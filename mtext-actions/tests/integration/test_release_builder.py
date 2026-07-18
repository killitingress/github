from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.config import load_mandant_config, load_releaselinien
from lbs_delivery.git_refs import (
    diff_name_status,
    is_ancestor,
    previous_release_tag,
    resolve_commit,
)
from lbs_delivery.manifest import load_manifest, verify_artifacts
from lbs_delivery.paths import sha256_file
from lbs_delivery.release import build_release


# Wurzel des zentralen Automationsprojekts mit produktionsnahen Testkonfigurationen.
AUTOMATION_ROOT = Path(__file__).resolve().parents[2]


def git(repository: Path, *arguments: str) -> str:
    """Führt einen Git-Befehl im temporären Test-Repository aus."""

    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


class ReleaseBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt eine vollständige Tag- und Änderungshistorie für Releasetests."""

        # Das Repository bildet FULL-Basis, Vorgänger und Zielrelease real mit Git ab.
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "mtext-fi"
        self.repository.mkdir()
        git(self.repository, "init", "-b", "R261/Bereitstellung")
        git(self.repository, "config", "user.name", "Test")
        git(self.repository, "config", "user.email", "test@example.invalid")
        for project in (
            "Configuration",
            "Fonts",
            "LOMS_Framework",
            "LOMS_Basis",
            "LOMS_PKA",
        ):
            path = self.repository / project
            path.mkdir()
            (path / "baseline.txt").write_text(f"{project}\n", encoding="utf-8")
        (self.repository / "LOMS_Basis/deleted.txt").write_text(
            "delete me\n", encoding="utf-8"
        )
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "full")
        git(self.repository, "tag", "R261.100")
        (self.repository / "LOMS_Basis/baseline.txt").write_text(
            "changed\n", encoding="utf-8"
        )
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "intermediate")
        git(self.repository, "tag", "R261.107")
        (self.repository / "LOMS_Basis/deleted.txt").unlink()
        (self.repository / "LOMS_Basis/new.txt").write_text("new\n", encoding="utf-8")
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-m", "delta")
        git(self.repository, "tag", "R261.108")
        git(
            self.repository,
            "update-ref",
            "refs/remotes/origin/R261/Bereitstellung",
            "HEAD",
        )
        self.mandant = load_mandant_config(
            AUTOMATION_ROOT / "tests/fixtures/mandant.json",
            repository_name="mtext-fi",
        )
        self.releaselinien = load_releaselinien(
            AUTOMATION_ROOT / "config/releaselinien.json"
        )

    def tearDown(self) -> None:
        """Entfernt das temporäre Repository nach jedem Testlauf."""

        self.temporary.cleanup()

    def test_full_and_cumulative_delta_release(self) -> None:
        """Prüft kumulatives DELTA, reproduzierbare Archive und vollständiges FULL."""

        # DELTA reicht zur .100-Basis zurück; die Information nutzt den
        # direkten Vorgänger.
        base_sha = resolve_commit(self.repository, "R261.100")
        target_sha = resolve_commit(self.repository, "R261.108")
        previous_sha = resolve_commit(self.repository, "R261.107")
        self.assertEqual(previous_release_tag(self.repository, "R261.108"), "R261.107")
        self.assertTrue(is_ancestor(self.repository, base_sha, target_sha))
        self.assertFalse(is_ancestor(self.repository, target_sha, base_sha))
        changes = diff_name_status(self.repository, base_sha, target_sha)
        self.assertTrue(any(item.path == "LOMS_Basis/baseline.txt" for item in changes))

        first = self.root / "first"
        second = self.root / "second"
        first_manifest_path = build_release(
            self.repository,
            first,
            self.mandant,
            repository_name="mtext-fi",
            release_tag="R261.108",
            uebergabeprofil_name=self.releaselinien["R261"]["uebergabeprofil"],
            target_sha=target_sha,
            base_sha=base_sha,
            previous_tag="R261.107",
            previous_sha=previous_sha,
        )
        second_manifest_path = build_release(
            self.repository,
            second,
            self.mandant,
            repository_name="mtext-fi",
            release_tag="R261.108",
            uebergabeprofil_name=self.releaselinien["R261"]["uebergabeprofil"],
            target_sha=target_sha,
            base_sha=base_sha,
            previous_tag="R261.107",
            previous_sha=previous_sha,
        )
        first_manifest = load_manifest(first_manifest_path)
        second_manifest = load_manifest(second_manifest_path)
        # Zwei unabhängige Builds desselben Stands müssen bytegleiche Pakete erzeugen.
        verify_artifacts(first_manifest, first)
        verify_artifacts(second_manifest, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(
            sha256_file(first / "FIBASISD.tgz"),
            sha256_file(second / "FIBASISD.tgz"),
        )

        with tarfile.open(first / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion_list = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion_list)
            deleted = deletion_list.read().decode("utf-8")
        self.assertIn("LOMS_Basis/baseline.txt", names)
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)
        info = first / "_INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt"
        info_text = info.read_text(encoding="utf-8")
        direct_change_lines = "\n".join(
            line
            for line in info_text.splitlines()
            if line.startswith(("A", "M", "D"))
        )
        self.assertNotIn("baseline.txt", direct_change_lines)

        git(self.repository, "checkout", "--detach", "R261.100")
        target_sha = resolve_commit(self.repository, "R261.100")
        output = self.root / "full"
        manifest_path = build_release(
            self.repository,
            output,
            self.mandant,
            repository_name="mtext-fi",
            release_tag="R261.100",
            uebergabeprofil_name=self.releaselinien["R261"]["uebergabeprofil"],
            target_sha=target_sha,
            base_sha=None,
            previous_tag=None,
            previous_sha=None,
        )
        manifest = load_manifest(manifest_path)
        # FULL enthält den gesamten Basisstand und keine DELTA-Löschliste.
        self.assertEqual(manifest["delivery_type"], "FULL")
        self.assertFalse((output / "FIBASISD.tgz").exists())
        with tarfile.open(output / "FIBASISF.tgz", "r:gz") as archive:
            names = archive.getnames()
        self.assertIn("./LOMS_Basis/baseline.txt", names)
        self.assertIn("./LOMS_Basis/deleted.txt", names)
        self.assertTrue(
            (
                output
                / "_INFO_FI-LOMS_Basis-FULL-R261.100-R001.100.txt"
            ).is_file()
        )

    def test_information_uses_repository_source_path_for_changes(self) -> None:
        """Ordnet Git-Änderungen über den konfigurierten Repositorypfad zu."""

        repository = self.root / "nested-source"
        project_root = repository / "sources/LOMS_Basis"
        project_root.mkdir(parents=True)
        git(repository, "init", "-b", "R261/Bereitstellung")
        git(repository, "config", "user.name", "Test")
        git(repository, "config", "user.email", "test@example.invalid")
        (project_root / "value.txt").write_text("base\n", encoding="utf-8")
        git(repository, "add", ".")
        git(repository, "commit", "-m", "full")
        git(repository, "tag", "R261.100")
        (project_root / "value.txt").write_text("changed\n", encoding="utf-8")
        git(repository, "add", ".")
        git(repository, "commit", "-m", "delta")
        git(repository, "tag", "R261.101")

        mandant = {
            **self.mandant,
            "projects": [
                {"name": "LOMS_Basis", "source_path": "sources/LOMS_Basis"}
            ],
        }
        output = self.root / "nested-output"
        build_release(
            repository,
            output,
            mandant,
            repository_name="mtext-fi",
            release_tag="R261.101",
            uebergabeprofil_name=self.releaselinien["R261"]["uebergabeprofil"],
            target_sha=resolve_commit(repository, "R261.101"),
            base_sha=resolve_commit(repository, "R261.100"),
            previous_tag="R261.100",
            previous_sha=resolve_commit(repository, "R261.100"),
        )

        information = (
            output / "_INFO_FI-LOMS_Basis-DELTA-R261.101-R261.100.txt"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "M       VORRELEASE/sources/LOMS_Basis/value.txt", information
        )


if __name__ == "__main__":
    unittest.main()
