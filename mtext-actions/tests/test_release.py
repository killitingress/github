"""Prüft FULL- und DELTA-Pakete sowie ihre Mainframe-Übergabe."""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.mainframe_release import _submit_package, build_release, publish_mainframe
from lbs_delivery.process import DeliveryError, NETWORK_TIMEOUT, Status

from tests.support import (
    TempDirTestCase,
    approve_release_tag,
    git,
    jcl_template,
    load_test_configuration,
    setup_release_repository,
)


class ReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        """Bereitet eine Releasehistorie und beide Freigabewege vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.template = jcl_template()

        # Das DELTA durchläuft den Standardweg mit Freigabe-Pull-Request, das
        # FULL die konfigurierte Ausnahme mit direkt erstelltem Tag.
        self.configuration = load_test_configuration(self.repository)
        self.direct = load_test_configuration(
            self.repository, mandant={"releasefreigabe": "direkter_tag"}
        )
        approve_release_tag(self.repository, self.configuration, "v261.108")

    def build(self, output_directory: Path, *, tag: str, trigger_sha: str) -> None:
        """Erzeugt ein Releaseartefakt für den angegebenen Test-Tag."""

        build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=output_directory,
            jcl_template=self.template,
            tag=tag,
            trigger_sha=trigger_sha,
        )

    def test_release_files_and_mainframe_transfer(self) -> None:
        """Prüft Paketinhalt, JCL und die vorbereitete Mainframe-Übergabe."""

        git(self.repository, "checkout", "--detach", "v261.108")
        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        self.build(first, tag="v261.108", trigger_sha=target_sha)
        self.build(second, tag="v261.108", trigger_sha=target_sha)

        information = json.loads(next(first.glob("_INFO_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(information["projekt"], "LOMS_Basis")
        self.assertEqual(information["stand"]["von"]["referenz"], "v261.100")
        self.assertEqual(information["stand"]["bis"]["referenz"], "v261.108")
        self.assertIn(["D", "deleted.txt"], information["elemente"])
        self.assertIn(["A", "new.txt"], information["elemente"])
        self.assertIn(["D", "rename-old.txt"], information["elemente"])
        self.assertIn(["A", "rename-new.txt"], information["elemente"])
        self.assertEqual(
            information["sha256"]["D"],
            hashlib.sha256((first / "FIBASISD.tgz").read_bytes()).hexdigest(),
        )

        with tarfile.open(first / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion)
            deleted = deletion.read().decode()
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)

        with (
            patch.dict(
                os.environ,
                {
                    "MAINFRAME_FTPS_HOST": "mainframe.example",
                    "MAINFRAME_FTPS_PORT": "2121",
                    "MAINFRAME_FTPS_USER": "user",
                    "MAINFRAME_FTPS_PASSWORD": "password",
                },
            ),
            patch("lbs_delivery.mainframe_release._submit_package") as submit,
        ):
            result = publish_mainframe(artifact_root=first)
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once_with(
            first / "FIBASISD.tgz",
            first / "FIBASISD.jcl",
            "FIBASISD",
            host="mainframe.example",
            port=2121,
            user="user",
            password="password",
        )
        rendered = (first / "FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        (second / "FIBASISD.jcl").unlink()
        with self.assertRaisesRegex(DeliveryError, "Releasepakete oder JCL fehlen"):
            publish_mainframe(artifact_root=second)

        git(self.repository, "checkout", "--detach", "v261.100")
        full = self.root / "full"
        build_release(
            self.direct,
            repository_root=self.repository,
            output_directory=full,
            jcl_template=self.template,
            tag="v261.100",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        self.assertEqual(sorted(package.stem for package in full.glob("*.tgz")), ["FIBASISD", "FIBASISF"])
        full_information = json.loads(next(full.glob("_INFO_*.json")).read_text(encoding="utf-8"))
        self.assertNotIn("von", full_information["stand"])
        self.assertEqual(set(full_information["sha256"]), {"F", "D"})
        self.assertTrue(all(element[0] == "A" for element in full_information["elemente"]))

        git(self.repository, "update-ref", "-d", "refs/remotes/origin/release/R261")
        git(self.repository, "update-ref", "refs/remotes/origin/main", target_sha)
        with self.assertRaises(DeliveryError):
            self.build(self.root / "wrong-main-line", tag="v261.108", trigger_sha=target_sha)

    def test_submits_package_and_jcl_with_explicit_ftps(self) -> None:
        """Prüft TLS-Aushandlung, geschützte Datenverbindung und JES-Übergabe."""

        package = self.root / "FIBASISD.tgz"
        package.write_bytes(b"package")
        jcl = self.root / "FIBASISD.jcl"
        jcl.write_text("//TEST JOB\n", encoding="ascii")

        with (
            patch("lbs_delivery.mainframe_release.ssl.create_default_context") as create_context,
            patch("lbs_delivery.mainframe_release.ftplib.FTP_TLS") as ftp_tls,
        ):
            _submit_package(
                package,
                jcl,
                "FIBASISD",
                host="mainframe.example",
                port=2121,
                user="user",
                password="password",
            )

        create_context.assert_called_once_with()
        ftp_tls.assert_called_once_with(context=create_context.return_value)
        session = ftp_tls.return_value
        session.connect.assert_called_once_with("mainframe.example", 2121, timeout=NETWORK_TIMEOUT)
        session.login.assert_called_once_with("user", "password")
        session.prot_p.assert_called_once_with()
        session.set_pasv.assert_called_once_with(True)
        self.assertEqual(session.storbinary.call_args.args[0], "STOR 'IEA.LOMS.TONICZ(FIBASISD)'")
        session.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
        self.assertEqual(session.storlines.call_args.args[0], "STOR LIT9028A")
        session.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
