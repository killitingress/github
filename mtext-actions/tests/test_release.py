"""Prüft FULL- und DELTA-Pakete sowie ihre Mainframe-Übergabe."""

from __future__ import annotations

import os
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.release import build_release

from tests.support import TempDirTestCase, git, jcl_template, load_test_configuration, setup_release_repository


class ReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.template = jcl_template()

    def build(self, output_directory: Path, *, tag: str, trigger_sha: str) -> None:
        build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=output_directory,
            jcl_template=self.template,
            tag=tag,
            trigger_sha=trigger_sha,
        )

    def test_release_files_and_mainframe_transfer(self) -> None:
        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        self.build(first, tag="v261.108", trigger_sha=target_sha)
        self.build(second, tag="v261.108", trigger_sha=target_sha)
        self.assertEqual((first / "FIBASISD.tgz").read_bytes(), (second / "FIBASISD.tgz").read_bytes())

        information = next(first.glob("_INFO_*.txt")).read_text(encoding="utf-8")
        for fragment in (
            "D       VORRELEASE/LOMS_Basis/deleted.txt",
            "A       VORRELEASE/LOMS_Basis/new.txt",
            "D       VORRELEASE/LOMS_Basis/rename-old.txt",
            "A       VORRELEASE/LOMS_Basis/rename-new.txt",
            "LOMS_Basis/new.txt",
        ):
            self.assertIn(fragment, information)

        with tarfile.open(first / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion)
            deleted = deletion.read().decode("utf-8")
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)

        with (
            patch.dict(
                os.environ,
                {
                    "MAINFRAME_FTP_HOST": "mainframe.example",
                    "MAINFRAME_FTP_USER": "user",
                    "MAINFRAME_FTP_PASSWORD": "password",
                },
            ),
            patch("lbs_delivery.mainframe.submit_package") as submit,
        ):
            result = publish_mainframe(artifact_root=first)
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once()
        rendered = (first / "FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        (second / "FIBASISD.jcl").unlink()
        with self.assertRaisesRegex(DeliveryError, "Releasepakete oder JCL fehlen"):
            publish_mainframe(artifact_root=second)

        git(self.repository, "checkout", "--detach", "v261.100")
        full = self.root / "full"
        self.build(full, tag="v261.100", trigger_sha=git(self.repository, "rev-parse", "HEAD"))
        self.assertEqual(sorted(package.stem for package in full.glob("*.tgz")), ["FIBASISD", "FIBASISF"])

        git(self.repository, "update-ref", "-d", "refs/remotes/origin/release/R261")
        git(self.repository, "update-ref", "refs/remotes/origin/main", target_sha)
        with self.assertRaises(DeliveryError):
            self.build(self.root / "wrong-main-line", tag="v261.108", trigger_sha=target_sha)


if __name__ == "__main__":
    unittest.main()
