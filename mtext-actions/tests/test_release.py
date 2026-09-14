"""Prüft FULL- und DELTA-Archive sowie ihre Mainframe-Übergabe."""

from __future__ import annotations

import os
import shutil
import ssl
import tarfile
import unittest
from unittest.mock import call, patch

from lbs_delivery.mainframe import _submit_archive, run
from lbs_delivery.process import DeliveryError, NETWORK_TIMEOUT, Status

from tests.support import (
    TempDirTestCase,
    git,
    load_test_configuration,
    setup_release_repository,
)


class ReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        """Bereitet eine Releasehistorie für FULL und DELTA vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.runner_temp = self.root / "runner-temp"
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(self.root),
            "GITHUB_REPOSITORY": self.configuration.repository,
            "RUNNER_TEMP": str(self.runner_temp),
            # lokale macOS-Läufe erzeugen wie der Linux-Runner keine AppleDouble-Dateien
            "COPYFILE_DISABLE": "1",
        }))

    def test_release_files_and_mainframe_transfer(self) -> None:
        """Prüft DELTA und FULL vom Paketbau im Runner bis zur Mainframe-Übergabe."""

        # Paketbau verwendet den vorbereiteten Commit, bevor der Liefer-Tag existiert
        git(self.repository, "checkout", "--detach", "r261.108")
        git(self.repository, "tag", "-d", "r261.108")
        git(self.repository, "commit", "--allow-empty", "-m", "bereitstellung")
        stale_dist = self.root / "dist"
        stale_dist.mkdir()
        (stale_dist / "alt.tgz").write_bytes(b"alter Lauf")

        # die Workflow-Einstiege verwenden das erzeugte und anschließend heruntergeladene Artefakt
        result = run("build", tag="r261.108")
        self.assertEqual(result["status"], Status.ARTIFACT_READY)
        delivery = self.runner_temp / "release"
        shutil.copytree(self.runner_temp / "dist", delivery)

        # das Artefakt enthält ausschließlich Mainframe-Dateien
        self.assertEqual(sorted(e.name for e in delivery.iterdir()), ["FIBASISD.jcl", "FIBASISD.tgz"])

        # Archiv und Löschliste beziehen sich auf .100 und enthalten keinen transient-Eintrag
        with tarfile.open(delivery / "FIBASISD.tgz", "r:gz") as archive:
            self.assertEqual(
                {e.name: archive.extractfile(e).read() for e in archive.getmembers() if e.isfile()},
                {
                    "LOMS_Basis/baseline.txt": b"changed\n",
                    "LOMS_Basis/new.txt": b"new\n",
                    "LOMS_Basis/rename-new.txt": b"rename\n",
                    "FIBASISD.txt": b"LOMS_Basis/deleted.txt\nLOMS_Basis/rename-old.txt\n",
                },
            )

        # Übergabe verwendet die erzeugte JCL und beendet einen unvollständigen Lieferbestand
        with patch("lbs_delivery.mainframe._submit_archive") as submit:
            result = run("mainframe")
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED)
        submit.assert_called_once_with(delivery / "FIBASISD.tgz")
        rendered = (delivery / "FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        # Dry Run prüft denselben Artefaktbestand, öffnet aber keine FTPS-Sitzung
        with patch.dict(os.environ, {"DRY_RUN": "true"}), patch("lbs_delivery.mainframe._submit_archive") as submit:
            result = run("mainframe")
        self.assertEqual(result["status"], Status.MAINFRAME_SKIPPED)
        submit.assert_not_called()

        (delivery / "FIBASISD.jcl").unlink()
        with self.assertRaises(DeliveryError) as raised:
            run("mainframe")
        self.assertEqual(raised.exception.status, Status.PACKAGE_FAILED)
        self.assertEqual((stale_dist / "alt.tgz").read_bytes(), b"alter Lauf")

        # die angenommene Zwischenlieferung wird vor dem nächsten Hauptrelease gekennzeichnet
        git(self.repository, "tag", "r261.108")

        # ein neues Hauptrelease folgt auf die vorhandene Zwischenlieferung
        (self.repository / "LOMS_Basis/new.txt").unlink()
        git(self.repository, "add", "-u")
        git(self.repository, "commit", "-m", "neues Hauptrelease")

        # FULL erstellt den vollständigen Projektstand und ein leeres D-Archiv
        run("build", tag="r270.100")
        shutil.copytree(self.runner_temp / "dist", delivery, dirs_exist_ok=True)
        self.assertEqual(sorted(e.stem for e in delivery.glob("*.tgz")), ["FIBASISD", "FIBASISF"])
        self.assertEqual(sorted(e.name for e in (self.runner_temp / "dist").iterdir()), [
            "FIBASISD.jcl", "FIBASISD.tgz", "FIBASISF.jcl", "FIBASISF.tgz",
        ])
        with tarfile.open(delivery / "FIBASISF.tgz") as archive:
            self.assertEqual(
                {e.name: archive.extractfile(e).read() for e in archive.getmembers() if e.isfile()},
                {"./LOMS_Basis/baseline.txt": b"changed\n", "./LOMS_Basis/rename-new.txt": b"rename\n"},
            )
        with tarfile.open(delivery / "FIBASISD.tgz") as archive:
            self.assertEqual(archive.extractfile("FIBASISD.txt").read(), b"")
        # FULL übernimmt erst den Projektstand und ersetzt danach das alte D-Archiv
        with patch("lbs_delivery.mainframe._submit_archive") as submit:
            run("mainframe")
        self.assertEqual(submit.call_args_list, [call(delivery / "FIBASISF.tgz"), call(delivery / "FIBASISD.tgz")])

        archive = delivery / "FIBASISD.tgz"
        jcl = delivery / "FIBASISD.jcl"
        with (
            patch.dict(os.environ, {"IZE9_FTPS_PASSWORD_MTEXT": "password"}),
            patch("lbs_delivery.mainframe.ssl.SSLContext") as create_context,
            patch("lbs_delivery.mainframe.ftplib.FTP_TLS") as ftp_tls,
        ):
            _submit_archive(archive)

        create_context.assert_called_once_with(ssl.PROTOCOL_TLS_CLIENT)
        context = create_context.return_value
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        ftp_tls.assert_called_once_with(context=context)
        session = ftp_tls.return_value
        session.connect.assert_called_once_with("ize9.lbs-it.de", 21, timeout=NETWORK_TIMEOUT)
        session.login.assert_called_once_with("LIT9028", "password")
        session.prot_p.assert_called_once_with()
        self.assertEqual(session.storbinary.call_args.args[0], "STOR 'IEA.LOMS.TONICZ(FIBASISD)'")
        session.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
        self.assertEqual(session.storlines.call_args.args[0], "STOR LIT9028A")
        session.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
