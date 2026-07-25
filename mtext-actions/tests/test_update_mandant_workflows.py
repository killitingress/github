"""Prüft die Vorbereitung der Mandanten-Aktualisierungen."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from workflow_configuration import (
    UPDATE_WORKFLOW,
    build_update_matrix,
    prepare_automation_update,
    prepare_mandant_update,
)


# Diese Wurzel enthält die Aktualisierungslogik und die zentralen Workflowvorlagen.
ROOT = Path(__file__).resolve().parents[1]


class UpdateWorkflowsTests(unittest.TestCase):
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

    def test_prepares_verified_workflow_updates_idempotently(self) -> None:
        """Prüft Rollout, Mandanten-Pins, SHA-Ablehnung und Wiederholbarkeit."""

        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "freigegebenen SHA"):
            prepare_automation_update(self.automation_root, "fi-runner", "1" * 40)

        with redirect_stderr(io.StringIO()):
            automation_sha = prepare_automation_update(
                self.automation_root,
                "fi-runner",
                initial_sha,
            )
            mandant_sha = prepare_mandant_update(
                self.automation_root,
                self.mandant_root,
                automation_sha,
            )
        self.assertNotEqual(automation_sha, initial_sha)
        self.assertEqual(
            self.mandant_workflow.read_text(encoding="utf-8").count(automation_sha),
            2,
        )

        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8")
            if path.name == UPDATE_WORKFLOW:
                self.assertIn("runs-on: ${{ vars.FI_RUNNER_LABEL }}", workflow)
            else:
                self.assertNotIn("FI_RUNNER_LABEL_TO_BE_SET", workflow)
                self.assertIn('runs-on: "fi-runner"', workflow)

        with redirect_stderr(io.StringIO()):
            self.assertEqual(
                prepare_automation_update(
                    self.automation_root, "fi-runner", automation_sha
                ),
                automation_sha,
            )
            self.assertEqual(
                prepare_mandant_update(
                    self.automation_root, self.mandant_root, automation_sha
                ),
                mandant_sha,
            )

    def test_builds_update_matrix(self) -> None:
        """Bildet alle Mandantenbranches aus Zuordnung, Releaselinien und Stufen."""

        mandanten = self.root / "mandanten.json"
        mandanten.write_text(
            json.dumps(
                {
                    "FI": {
                        "repository": "<oms_team>/mtext-fi",
                        "subsystem": "LOMS",
                    },
                    "BY": {
                        "repository": "<oms_team>/mtext-by",
                        "subsystem": "BYMT",
                    },
                }
            ),
            encoding="utf-8",
        )
        releaselinien = self.root / "releaselinien.json"
        releaselinien.write_text(
            json.dumps(
                {
                    "R261": {"etaps_linie": "en01", "hostprofil": "FKT"},
                    "R270": {"etaps_linie": "en02", "hostprofil": "JUR"},
                }
            ),
            encoding="utf-8",
        )

        matrix = build_update_matrix(mandanten, releaselinien)["include"]

        self.assertEqual(len(matrix), 12)
        self.assertIn(
            {
                "repository": "<oms_team>/mtext-fi",
                "kuerzel": "FI",
                "branch": "R261/Entwicklung",
            },
            matrix,
        )


if __name__ == "__main__":
    unittest.main()
