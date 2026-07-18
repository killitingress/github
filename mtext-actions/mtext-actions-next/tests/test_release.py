"""Prüft den vollständigen FULL-/DELTA- und Publish-Vertrag."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.config import load_configuration
from lbs_delivery.errors import DeliveryError
from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.manifest import load_and_verify, sha256_file
from lbs_delivery.release import build_release

from tests.support import git, write_mandant


# Diese Wurzel enthält die neue Releaselinienzuordnung und das JCL-Template.
AUTOMATION_ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt FULL-Basis, direkten Vorgänger und DELTA-Ziel mit Git."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "mtext-fi"
        self.repository.mkdir()
        git(self.repository, "init", "-b", "R261/Bereitstellung")
        git(self.repository, "config", "user.name", "Test")
        git(self.repository, "config", "user.email", "test@example.invalid")
        project = self.repository / "LOMS_Basis"
        project.mkdir()
        (project / "baseline.txt").write_text("base\n", encoding="utf-8")
        (project / "deleted.txt").write_text("delete\n", encoding="utf-8")
        (project / "rename-old.txt").write_text("rename\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "full")
        git(self.repository, "tag", "R261.100")
        (project / "baseline.txt").write_text("changed\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "previous")
        git(self.repository, "tag", "R261.107")
        (project / "deleted.txt").unlink()
        (project / "new.txt").write_text("new\n", encoding="utf-8")
        git(
            self.repository,
            "mv",
            "LOMS_Basis/rename-old.txt",
            "LOMS_Basis/rename-new.txt",
        )
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-m", "delta")
        git(self.repository, "tag", "R261.108")
        git(
            self.repository,
            "update-ref",
            "refs/remotes/origin/R261/Bereitstellung",
            "HEAD",
        )
        self.mandant_path = self.root / "mandant.json"
        write_mandant(self.mandant_path)
        self.configuration = load_configuration(
            self.mandant_path,
            AUTOMATION_ROOT / "config/releaselinien.json",
            repository_name="mtext-fi",
            repository_root=self.repository,
        )

    def test_full_delta_and_publish_dry_run(self) -> None:
        """Prüft Archivvertrag, Reproduzierbarkeit, Manifest und gerenderte JCL."""

        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        first_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=first,
            repository_name="mtext-fi",
            tag="R261.108",
            trigger_sha=target_sha,
        )
        second_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=second,
            repository_name="mtext-fi",
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
        self.assertIn("LOMS_Basis/baseline.txt", names)
        self.assertIn("LOMS_Basis/rename-new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)
        self.assertIn("LOMS_Basis/rename-old.txt", deleted)

        information = (
            first / "_INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("D       VORRELEASE/LOMS_Basis/rename-old.txt", information)
        self.assertIn("A       VORRELEASE/LOMS_Basis/rename-new.txt", information)

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
        full = self.root / "full"
        full_manifest = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=full,
            repository_name="mtext-fi",
            tag="R261.100",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        load_and_verify(full_manifest, full)
        with tarfile.open(full / "FIBASISF.tgz", "r:gz") as archive:
            full_names = archive.getnames()
        self.assertIn("./LOMS_Basis/baseline.txt", full_names)
        self.assertIn("./LOMS_Basis/deleted.txt", full_names)

    def test_publish_rejects_changed_artifact(self) -> None:
        """Lehnt eine Paketänderung nach dem Releasebau vor der Übergabe ab."""

        output = self.root / "tampered"
        manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=output,
            repository_name="mtext-fi",
            tag="R261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        (output / "FIBASISD.tgz").write_bytes(b"tampered")
        with self.assertRaises(DeliveryError):
            load_and_verify(manifest_path, output)


if __name__ == "__main__":
    unittest.main()
