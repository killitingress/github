"""Prüft den vollständigen Vertrag für FULL, DELTA, Manifest und Übergabe."""

from __future__ import annotations

import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.manifest import load_and_verify, sha256_file
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.release import build_release

from tests.support import AUTOMATION_ROOT, git, load_test_configuration, setup_release_repository


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt eine mit Release-Tags versehene Historie und lädt ihre Konfiguration."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)

    def test_release_delivery_contract(self) -> None:
        """Prüft reproduzierbare Pakete, Manifest, JCL und Abwehr an Integritätsgrenzen."""

        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        first_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=first,
            tag="v261.108",
            trigger_sha=target_sha,
        )
        second_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=second,
            tag="v261.108",
            trigger_sha=target_sha,
        )
        first_manifest, packages = load_and_verify(first_manifest_path, first)
        second_manifest, _ = load_and_verify(second_manifest_path, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(sha256_file(first / "FIBASISD.tgz"), sha256_file(second / "FIBASISD.tgz"))
        self.assertEqual([item["member"] for item in packages], ["FIBASISD"])
        information = next(item for item in first_manifest["artifacts"] if item["kind"] == "information")
        self.assertEqual(
            information["changes"],
            [
                {"status": "D", "path": "LOMS_Basis/deleted.txt"},
                {"status": "A", "path": "LOMS_Basis/new.txt"},
                {"status": "D", "path": "LOMS_Basis/rename-old.txt"},
                {"status": "A", "path": "LOMS_Basis/rename-new.txt"},
            ],
        )
        self.assertIn("LOMS_Basis/new.txt", information["archive_entries"])

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
            result = publish_mainframe(
                manifest_path=first_manifest_path,
                artifact_root=first,
                template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
                temporary_directory=self.root / "jcl",
            )
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once()
        rendered = (self.root / "jcl/FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        git(self.repository, "checkout", "--detach", "v261.100")
        full_manifest = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.root / "full",
            tag="v261.100",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        _manifest, full_packages = load_and_verify(full_manifest, self.root / "full")
        self.assertEqual([package["member"] for package in full_packages], ["FIBASISF", "FIBASISD"])

        with self.subTest(informationsdatei_manipuliert=True):
            second_information = next(
                item for item in second_manifest["artifacts"] if item["kind"] == "information"
            )
            (second / second_information["path"]).write_text("manipuliert", encoding="utf-8")
            with self.assertRaises(DeliveryError):
                load_and_verify(second_manifest_path, second)

        with self.subTest(manipuliert=True):
            (first / "FIBASISD.tgz").write_bytes(b"tampered")
            with self.assertRaises(DeliveryError):
                load_and_verify(first_manifest_path, first)

        with self.subTest(main_releaselinie=False):
            git(self.repository, "update-ref", "-d", "refs/remotes/origin/release/R261")
            git(self.repository, "update-ref", "refs/remotes/origin/main", target_sha)
            with self.assertRaises(DeliveryError):
                build_release(
                    self.configuration,
                    repository_root=self.repository,
                    output_directory=self.root / "wrong-main-line",
                    tag="v261.108",
                    trigger_sha=target_sha,
                )


if __name__ == "__main__":
    unittest.main()
