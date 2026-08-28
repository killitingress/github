"""Prüft FULL- und DELTA-Pakete sowie ihre Mainframe-Übergabe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.mainframe_release import _submit_package, _build_release, _publish_mainframe, run
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
        self._workspace = patch.dict(os.environ, {"GITHUB_WORKSPACE": str(self.root)})
        self._workspace.start()
        self.addCleanup(self._workspace.stop)

    def build(self, output_directory: Path, *, tag: str) -> None:
        """Erzeugt ein Releaseartefakt für den angegebenen Test-Tag."""

        _build_release(self.configuration, output_directory=output_directory, tag=tag)

    def test_release_files_and_mainframe_transfer(self) -> None:
        """Prüft Paketinhalt, JCL und die vorbereitete Mainframe-Übergabe."""

        git(self.repository, "checkout", "--detach", "r261.108")
        first = self.root / "first"
        second = self.root / "second"
        self.build(first, tag="r261.108")
        self.build(second, tag="r261.108")

        information = json.loads(next(first.glob("_INFO_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(information["projekt"], "LOMS_Basis")
        self.assertEqual(information["stand"]["von"]["referenz"], "r261.100")
        self.assertEqual(information["stand"]["bis"]["referenz"], "r261.108")
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
                    "MAINFRAME_FTPS_PASSWORD": "password",
                },
            ),
            patch("lbs_delivery.mainframe_release._submit_package") as submit,
        ):
            result = _publish_mainframe(artifact_root=first)
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once_with(first / "FIBASISD.tgz")
        rendered = (first / "FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        (second / "FIBASISD.jcl").unlink()
        with self.assertRaisesRegex(DeliveryError, "Releasepakete oder JCL fehlen"):
            _publish_mainframe(artifact_root=second)

        git(self.repository, "checkout", "--detach", "r261.100")
        full = self.root / "full"
        _build_release(self.configuration, output_directory=full, tag="r261.100")
        self.assertEqual(sorted(package.stem for package in full.glob("*.tgz")), ["FIBASISD", "FIBASISF"])
        full_information = json.loads(next(full.glob("_INFO_*.json")).read_text(encoding="utf-8"))
        self.assertNotIn("von", full_information["stand"])
        self.assertEqual(set(full_information["sha256"]), {"F", "D"})
        self.assertTrue(all(element[0] == "A" for element in full_information["elemente"]))

    def test_submits_package_and_jcl_with_explicit_ftps(self) -> None:
        """Prüft TLS-Aushandlung, geschützte Datenverbindung und JES-Übergabe."""

        package = self.root / "FIBASISD.tgz"
        package.write_bytes(b"package")
        jcl = self.root / "FIBASISD.jcl"
        jcl.write_text("//TEST JOB\n", encoding="ascii")

        with (
            patch.dict(os.environ, {"MAINFRAME_FTPS_PASSWORD": "password"}),
            patch("lbs_delivery.mainframe_release.ssl.create_default_context") as create_context,
            patch("lbs_delivery.mainframe_release.ftplib.FTP_TLS") as ftp_tls,
        ):
            _submit_package(package)

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

    def test_workflow_builds_and_publishes_in_runner_temp(self) -> None:
        """Prüft Paketbau und Übergabe trotz vorhandener Dateien im Arbeitsbereich."""

        git(self.repository, "checkout", "--detach", "r261.108")
        stale_dist = self.root / "dist"
        stale_dist.mkdir()
        (stale_dist / "alt.tgz").write_bytes(b"alter Lauf")
        runner_temp = self.root / "runner-temp"

        with patch.dict(os.environ, {
            "GITHUB_REPOSITORY": self.configuration.repository,
            "RUNNER_TEMP": str(runner_temp),
        }):
            result = run(argparse.Namespace(release_command="build", tag="r261.108"))
            self.assertEqual(result["status"], Status.ARTIFACT_READY.value)

            # Bildet das Herunterladen des Build-Artefakts im Übergabejob nach.
            shutil.copytree(runner_temp / "dist", runner_temp / "release")
            with patch("lbs_delivery.mainframe_release._submit_package") as submit:
                result = run(argparse.Namespace(release_command="mainframe"))

        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once_with(runner_temp / "release/FIBASISD.tgz")
        self.assertEqual((stale_dist / "alt.tgz").read_bytes(), b"alter Lauf")

    def test_delta_need_not_lie_on_release_branch(self) -> None:
        """DELTA-Lieferungen dürfen auf einem Commit außerhalb von release/nnn liegen."""

        git(self.repository, "checkout", "--detach", "r261.108")
        git(self.repository, "commit", "--allow-empty", "-m", "bereitstellung")
        picked = git(self.repository, "rev-parse", "HEAD")
        git(self.repository, "tag", "-d", "r261.108")
        git(self.repository, "tag", "r261.108", picked)
        self.build(self.root / "picked-delta", tag="r261.108")


if __name__ == "__main__":
    unittest.main()
