"""Prüft den vollständigen FULL-/DELTA- und Publish-Vertrag."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError
from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.manifest import load_and_verify, sha256_file
from lbs_delivery.release import build_release

from tests.support import (
    AUTOMATION_ROOT,
    git,
    load_test_configuration,
    setup_release_repository,
)


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt FULL-Basis, direkten Vorgänger und DELTA-Ziel mit Git."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.root, self.repository)

    def test_builds_reproducible_full_and_delta_archives(self) -> None:
        """Prüft Archivvertrag, Reproduzierbarkeit, Manifest und gerenderte JCL."""

        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        first_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=first,
            repository_name="<oms_team>/mtext-fi",
            tag="R261.108",
            trigger_sha=target_sha,
        )
        second_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=second,
            repository_name="<oms_team>/mtext-fi",
            tag="R261.108",
            trigger_sha=target_sha,
        )
        first_manifest, packages = load_and_verify(first_manifest_path, first)
        second_manifest, _ = load_and_verify(second_manifest_path, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(
            sha256_file(first / "FIBASISD.tgz"),
            sha256_file(second / "FIBASISD.tgz"),
        )
        self.assertEqual([item["member"] for item in packages], ["FIBASISD"])

        with tarfile.open(first / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion)
            deleted = deletion.read().decode("utf-8")
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)

        result = publish_mainframe(
            manifest_path=first_manifest_path,
            artifact_root=first,
            template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
            temporary_directory=self.root / "jcl",
            execute=False,
        )
        self.assertEqual(result["packages"], ["FIBASISD"])
        rendered = (self.root / "jcl/FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        git(self.repository, "checkout", "--detach", "R261.100")
        full_manifest = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.root / "full",
            repository_name="<oms_team>/mtext-fi",
            tag="R261.100",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        _manifest, full_packages = load_and_verify(full_manifest, self.root / "full")
        self.assertEqual(
            [package["member"] for package in full_packages],
            ["FIBASISF", "FIBASISD"],
        )

    def test_rejects_tampered_release_artifact(self) -> None:
        """Lehnt eine Paketänderung nach dem Releasebau vor der Übergabe ab."""

        output = self.root / "tampered"
        manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=output,
            repository_name="<oms_team>/mtext-fi",
            tag="R261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        (output / "FIBASISD.tgz").write_bytes(b"tampered")
        with self.assertRaises(DeliveryError):
            load_and_verify(manifest_path, output)


if __name__ == "__main__":
    unittest.main()
