"""Prüft die vollständige Vorbereitung der zentralen Workflow-Commits."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workflow_configuration
from workflow_configuration import CONFIGURATION_WORKFLOW


# Diese Wurzel enthält die Einrichtungslogik und die zentralen Workflowvorlagen.
ROOT = Path(__file__).resolve().parents[1]
# Das Modul läuft wie im Einrichtungsworkflow als eigener Python-Prozess.
MODULE = "workflow_configuration"


class ConfigureWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt zwei getrennte temporäre Git-Repositories mit Workflowdateien."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automation_root = self.root / "automation"
        shutil.copytree(
            ROOT / ".github/workflows",
            self.automation_root / ".github/workflows",
        )

        self.mandant_root = self.root / "mandant"
        mandant_workflows = self.mandant_root / ".github/workflows"
        mandant_workflows.mkdir(parents=True)
        self.mandant_workflow = mandant_workflows / "sync-resources.yml"
        self.mandant_workflow.write_text(
            """jobs:
  sync-entwicklung:
    uses: j520730/mtext-actions/.github/workflows/reusable-sync-resources.yml@0000000000000000000000000000000000000000
    with:
      automation_ref: 0000000000000000000000000000000000000000
""",
            encoding="utf-8",
        )
        for repository in (self.automation_root, self.mandant_root):
            self.run_git(repository, "init", "-q")
            self.run_git(repository, "config", "user.name", "Test")
            self.run_git(repository, "config", "user.email", "test@example.invalid")
            self.run_git(repository, "add", ".")
            self.run_git(repository, "commit", "-q", "-m", "Ausgangsstand")

    def run_git(self, repository: Path, *arguments: str) -> str:
        """Führt eine erwartbar erfolgreiche Git-Operation im Test-Repository aus."""

        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def run_module(
        self,
        runner_label: str = "fi-runner",
        automation_sha: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Startet dieselbe einmalige Vorbereitung wie der GitHub-Workflow."""

        automation_sha = automation_sha or self.run_git(
            self.automation_root, "rev-parse", "HEAD"
        )
        return subprocess.run(
            [sys.executable, "-m", MODULE],
            check=False,
            capture_output=True,
            cwd=self.root,
            env={
                **os.environ,
                "AUTOMATION_SHA": automation_sha,
                "FI_RUNNER_LABEL": runner_label,
                "PYTHONPATH": str(ROOT / "src"),
            },
            text=True,
        )

    def test_prepares_verified_commits_in_sha_order_and_is_idempotent(self) -> None:
        """Prüft den vollständigen Zwei-Repository-Ablauf und seine Wiederholung."""

        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        result = self.run_module()
        self.assertEqual(result.returncode, 0, result.stderr)
        automation_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        mandant_sha = self.run_git(self.mandant_root, "rev-parse", "HEAD")
        self.assertNotEqual(automation_sha, initial_sha)
        self.assertIn(automation_sha, result.stdout)

        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8")
            if path.name == CONFIGURATION_WORKFLOW:
                self.assertIn("runs-on: ${{ vars.FI_RUNNER_LABEL }}", workflow)
            else:
                self.assertNotIn("FI_RUNNER_LABEL_TO_BE_SET", workflow)
                self.assertIn('runs-on: "fi-runner"', workflow)
        mandant_workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.assertEqual(mandant_workflow.count(automation_sha), 2)
        self.assertIn(
            "[skip ci]",
            self.run_git(self.mandant_root, "log", "-1", "--pretty=%s"),
        )
        repeated = self.run_module()
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(
            self.run_git(self.automation_root, "rev-parse", "HEAD"), automation_sha
        )
        self.assertEqual(
            self.run_git(self.mandant_root, "rev-parse", "HEAD"), mandant_sha
        )

    def test_rolls_out_an_explicit_new_automation_sha(self) -> None:
        """Bindet einen Mandanten ohne zentralen Folgecommit an die gewählte Version."""

        initial = self.run_module()
        self.assertEqual(initial.returncode, 0, initial.stderr)
        central_workflow = self.automation_root / ".github/workflows/ci.yml"
        central_workflow.write_text(
            central_workflow.read_text(encoding="utf-8") + "\n# Freigegebene Änderung\n",
            encoding="utf-8",
        )
        self.run_git(self.automation_root, "add", ".github/workflows/ci.yml")
        self.run_git(
            self.automation_root, "commit", "-q", "-m", "Neue zentrale Version"
        )
        freigegebene_sha = self.run_git(
            self.automation_root, "rev-parse", "HEAD"
        )

        result = self.run_module(automation_sha=freigegebene_sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.run_git(self.automation_root, "rev-parse", "HEAD"),
            freigegebene_sha,
        )
        self.assertEqual(
            self.mandant_workflow.read_text(encoding="utf-8").count(
                freigegebene_sha
            ),
            2,
        )

    def test_rejects_a_checkout_other_than_the_released_sha(self) -> None:
        """Verhindert einen Rollout aus einem anderen zentralen Commit."""

        result = self.run_module(automation_sha="1" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checkout entspricht nicht", result.stderr)

    def test_validates_every_file_before_creating_central_commit(self) -> None:
        """Lässt eine ungültige Mandantendatei ohne zentrale Änderung scheitern."""

        broken = self.mandant_root / ".github/workflows/broken.yml"
        broken.write_text("jobs: {}\n", encoding="utf-8")
        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")

        result = self.run_module()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Workflowreferenzen fehlen", result.stderr)
        self.assertEqual(
            self.run_git(self.automation_root, "rev-parse", "HEAD"), initial_sha
        )
        central = (self.automation_root / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("FI_RUNNER_LABEL_TO_BE_SET", central)

    def test_rejects_unconfirmed_runner_label(self) -> None:
        """Verhindert die Einrichtung mit dem technischen Runner-Platzhalter."""

        result = self.run_module(runner_label="FI_RUNNER_LABEL_TO_BE_SET")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Runner-Kennzeichen", result.stderr)

    def test_fails_when_final_verification_finds_a_remaining_change(self) -> None:
        """Macht den leeren Zielzustand zu einer verbindlichen Erfolgsbedingung."""

        original = workflow_configuration._automation_changes
        calls = 0

        def report_remaining_change(
            automation_root: Path, runner_label: str
        ) -> dict[Path, str]:
            """Simuliert ausschließlich bei der Abschlussprüfung eine Abweichung."""

            nonlocal calls
            calls += 1
            changes = original(automation_root, runner_label)
            if calls == 2:
                path = automation_root / ".github/workflows/ci.yml"
                changes[path] = path.read_text(encoding="utf-8")
            return changes

        with patch("builtins.print"), patch.object(
            workflow_configuration, "_automation_changes", side_effect=report_remaining_change
        ):
            with self.assertRaisesRegex(RuntimeError, "Einrichtungsprüfung"):
                workflow_configuration.prepare_workflow_configuration(
                    self.automation_root,
                    self.mandant_root,
                    "fi-runner",
                    self.run_git(self.automation_root, "rev-parse", "HEAD"),
                )

if __name__ == "__main__":
    unittest.main()
