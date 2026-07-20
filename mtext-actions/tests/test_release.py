"""Prüft den vollständigen FULL-/DELTA- und Publish-Vertrag."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status
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
        _manifest, full_packages = load_and_verify(full_manifest, full)
        self.assertEqual(
            [package["member"] for package in full_packages],
            ["FIBASISF", "FIBASISD"],
        )
        with tarfile.open(full / "FIBASISF.tgz", "r:gz") as archive:
            full_names = archive.getnames()
        self.assertIn("./LOMS_Basis/baseline.txt", full_names)
        self.assertIn("./LOMS_Basis/deleted.txt", full_names)

        with tarfile.open(full / "FIBASISD.tgz", "r:gz") as archive:
            reset_names = archive.getnames()
            reset_deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(reset_deletion)
            self.assertEqual(reset_deletion.read(), b"")
        self.assertEqual(reset_names, ["FIBASISD.txt", "LOMS_Basis"])

        full_publish = publish_mainframe(
            manifest_path=full_manifest,
            artifact_root=full,
            template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
            temporary_directory=self.root / "full-jcl",
            execute=False,
        )
        self.assertEqual(full_publish["packages"], ["FIBASISF", "FIBASISD"])

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

    def test_release_packages_new_project_with_derived_code(self) -> None:
        """Paketiert ein zusätzliches Projekt ohne gepflegte Projektzuordnung."""

        project = self.repository / "LOMS_Dokumente"
        project.mkdir()
        (project / "value.txt").write_text("content\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "additional project")
        git(self.repository, "tag", "R261.109")
        git(
            self.repository,
            "update-ref",
            "refs/remotes/origin/R261/Bereitstellung",
            "HEAD",
        )
        configuration = load_test_configuration(self.root, self.repository)
        output = self.root / "additional-project"
        manifest_path = build_release(
            configuration,
            repository_root=self.repository,
            output_directory=output,
            repository_name="mtext-fi",
            tag="R261.109",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        _manifest, packages = load_and_verify(manifest_path, output)
        self.assertIn("FIDOKUMD", [package["member"] for package in packages])
        self.assertTrue((output / "FIDOKUMD.tgz").is_file())

    def test_release_uses_mandant_ispw_instance(self) -> None:
        """Übernimmt die konfigurierte Testinstanz in Manifest und JCL."""

        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant={"ispw": "T"},
        )
        output = self.root / "test-instance"
        manifest_path = build_release(
            configuration,
            repository_root=self.repository,
            output_directory=output,
            repository_name="mtext-fi",
            tag="R261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        manifest, _packages = load_and_verify(manifest_path, output)
        self.assertEqual(manifest["jcl"]["ISPW"], "T")

        publish_mainframe(
            manifest_path=manifest_path,
            artifact_root=output,
            template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
            temporary_directory=self.root / "test-jcl",
            execute=False,
        )
        rendered = (self.root / "test-jcl/FIBASISD.jcl").read_text(
            encoding="ascii"
        )
        self.assertIn("DSN=IEA.ISPWT.BOAS.FKTE.TONICZ", rendered)
        self.assertIn("PARM='ISPT/WZZECIJ'", rendered)

    def test_delta_rejects_base_outside_target_history(self) -> None:
        """Lehnt eine `.100`-Basis außerhalb der Historie des Ziel-Tags ab."""

        git(self.repository, "checkout", "--orphan", "unrelated")
        git(self.repository, "commit", "--allow-empty", "-m", "unrelated")
        git(self.repository, "tag", "--force", "R261.100")
        git(self.repository, "checkout", "--detach", "R261.108")

        with self.assertRaises(DeliveryError) as context:
            build_release(
                self.configuration,
                repository_root=self.repository,
                output_directory=self.root / "invalid-base",
                repository_name="mtext-fi",
                tag="R261.108",
                trigger_sha=git(self.repository, "rev-parse", "HEAD"),
            )
        self.assertEqual(context.exception.status, Status.SOURCE_FAILED)


if __name__ == "__main__":
    unittest.main()
