"""Prüft FULL- und DELTA-Archive sowie ihre Mainframe-Übergabe."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
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

        # ein Liefer-Tag außerhalb des Release-Branches und alte Arbeitsdateien sind zulässig
        git(self.repository, "checkout", "--detach", "r261.108")
        git(self.repository, "commit", "--allow-empty", "-m", "bereitstellung")
        git(self.repository, "tag", "-f", "r261.108")
        stale_dist = self.root / "dist"
        stale_dist.mkdir()
        (stale_dist / "alt.tgz").write_bytes(b"alter Lauf")

        # die Workflow-Einstiege verwenden das erzeugte und anschließend heruntergeladene Artefakt
        result = run("build", tag="r261.108")
        self.assertEqual(result["status"], Status.ARTIFACT_READY.value)
        delivery = self.runner_temp / "release"
        shutil.copytree(self.runner_temp / "dist", delivery)

        # die Info zeigt Änderungen seit .107, einschließlich der zwischenzeitlichen Datei
        information = json.loads(next(delivery.glob("_INFO_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(information["projekt"], "LOMS_Basis")
        self.assertEqual(information["scope"]["von"]["referenz"], "r261.107")
        self.assertEqual(information["scope"]["bis"]["referenz"], "r261.108")
        self.assertIn(["D", "deleted.txt"], information["elemente"])
        self.assertIn(["A", "new.txt"], information["elemente"])
        self.assertIn(["D", "rename-old.txt"], information["elemente"])
        self.assertIn(["A", "rename-new.txt"], information["elemente"])
        self.assertIn(["D", "transient.txt"], information["elemente"])
        self.assertNotIn(["M", "baseline.txt"], information["elemente"])
        self.assertEqual(
            information["sha256"],
            hashlib.sha256((delivery / "FIBASISD.tgz").read_bytes()).hexdigest(),
        )

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
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once_with(delivery / "FIBASISD.tgz")
        rendered = (delivery / "FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        (delivery / "FIBASISD.jcl").unlink()
        with self.assertRaisesRegex(DeliveryError, "Archive oder JCL fehlen"):
            run("mainframe")
        self.assertEqual((stale_dist / "alt.tgz").read_bytes(), b"alter Lauf")

        # ein neues Hauptrelease folgt auf die vorhandene Zwischenlieferung
        (self.repository / "LOMS_Basis/new.txt").unlink()
        git(self.repository, "add", "-u")
        git(self.repository, "commit", "-m", "neues Hauptrelease")
        git(self.repository, "tag", "r270.100")

        # der Berichtvergleich darf FULL nicht in ein DELTA umwandeln
        run("build", tag="r270.100")
        shutil.copytree(self.runner_temp / "dist", delivery, dirs_exist_ok=True)
        information = json.loads(next(delivery.glob("_INFO_*.json")).read_text())
        self.assertEqual(information["lieferart"], "FULL")
        self.assertEqual(information["scope"]["von"]["referenz"], "r261.108")
        self.assertEqual(information["elemente"], [["D", "new.txt"]])
        self.assertEqual(sorted(e.stem for e in delivery.glob("*.tgz")), ["FIBASISD", "FIBASISF"])
        self.assertEqual(information["sha256"], hashlib.sha256((delivery / "FIBASISF.tgz").read_bytes()).hexdigest())
        with tarfile.open(delivery / "FIBASISF.tgz") as archive:
            self.assertEqual(
                {e.name: archive.extractfile(e).read() for e in archive.getmembers() if e.isfile()},
                {"./LOMS_Basis/baseline.txt": b"changed\n", "./LOMS_Basis/rename-new.txt": b"rename\n"},
            )
        with tarfile.open(delivery / "FIBASISD.tgz") as archive:
            self.assertEqual(archive.extractfile("FIBASISD.txt").read(), b"")
        self.assertIn("Lieferart: `FULL`", (delivery / "lieferbericht.md").read_text())

        # FULL übernimmt erst den Projektstand und ersetzt danach das alte D-Archiv
        with patch("lbs_delivery.mainframe._submit_archive") as submit:
            run("mainframe")
        self.assertEqual(submit.call_args_list, [call(delivery / "FIBASISF.tgz"), call(delivery / "FIBASISD.tgz")])

    def test_submits_package_and_jcl_with_explicit_ftps(self) -> None:
        """Prüft TLS-Aushandlung, geschützte Datenverbindung und JES-Übergabe."""

        archive = self.root / "FIBASISD.tgz"
        archive.write_bytes(b"archive")
        jcl = self.root / "FIBASISD.jcl"
        jcl.write_text("//TEST JOB\n", encoding="ascii")

        with (
            patch.dict(os.environ, {"MAINFRAME_FTPS_PASSWORD": "password"}),
            patch("lbs_delivery.mainframe.ssl.create_default_context") as create_context,
            patch("lbs_delivery.mainframe.ftplib.FTP_TLS") as ftp_tls,
        ):
            _submit_archive(archive)

        create_context.assert_called_once_with()
        ftp_tls.assert_called_once_with(context=create_context.return_value)
        session = ftp_tls.return_value
        session.connect.assert_called_once_with("ize9.lbs-it.de", 21, timeout=NETWORK_TIMEOUT)
        session.login.assert_called_once_with("LIT9028", "password")
        session.prot_p.assert_called_once_with()
        session.set_pasv.assert_called_once_with(True)
        self.assertEqual(session.storbinary.call_args.args[0], "STOR 'IEA.LOMS.TONICZ(FIBASISD)'")
        session.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
        self.assertEqual(session.storlines.call_args.args[0], "STOR LIT9028A")
        session.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
