"""Prüft die Vorbereitung abgestimmter zentraler und mandantenseitiger Workflow-Aktualisierungen.

Temporäre Git-Repositories prüfen Commit-Grenzen, einheitliche Revisionsbindungen,
Wiederholbarkeit und Abdeckung der Rollout-Matrix, ohne echte Repositories zu
verändern.
"""

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


# Der Testaufbau kopiert die zentralen Workflows aus dem geprüften Automations-Checkout.
ROOT = Path(__file__).resolve().parents[1]


class UpdateWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt getrennte temporäre Automations- und Mandanten-Repositories.

        Unabhängige Historien bilden die tatsächliche Rollout-Grenze ab. Die
        Tests können damit prüfen, welches Repository den jeweiligen Commit erhält.
        """

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automation_root = self.root / "automation"
        shutil.copytree(ROOT / ".github/workflows", self.automation_root / ".github/workflows")

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
        """Führt eine erwartbar erfolgreiche Git-Operation mit hilfreicher Diagnose aus.

        Die Test-Assertion statt `check=True` nimmt stderr in die reguläre
        unittest-Fehlermeldung auf, wenn die Testhistorie nicht wie vorgesehen
        aufgebaut wurde.
        """

        command = ["git", "-C", str(repository), *arguments]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_prepares_verified_workflow_updates_idempotently(self) -> None:
        """Prüft Rollout-Commits, einheitliche Mandantenbindungen und Wiederholbarkeit.

        Eine abweichende zentrale SHA muss vor jeder Änderung scheitern.
        Erfolgreiche Wiederholungen müssen dieselben Commits behalten, sobald alle
        vorgesehenen Felder aktuell sind.
        """

        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "angegebenen Commit"):
            prepare_automation_update(self.automation_root, "fi-runner", "1" * 40)

        with redirect_stderr(io.StringIO()):
            automation_sha = prepare_automation_update(self.automation_root, "fi-runner", initial_sha)
            mandant_sha = prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha)
        self.assertNotEqual(automation_sha, initial_sha)
        self.assertEqual(self.mandant_workflow.read_text(encoding="utf-8").count(automation_sha), 2)

        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8")
            if path.name == UPDATE_WORKFLOW:
                self.assertIn("runs-on: ${{ vars.FI_RUNNER_LABEL }}", workflow)
            else:
                self.assertNotIn("FI_RUNNER_LABEL_TO_BE_SET", workflow)
                self.assertIn('runs-on: "fi-runner"', workflow)

        with redirect_stderr(io.StringIO()):
            self.assertEqual(
                prepare_automation_update(self.automation_root, "fi-runner", automation_sha),
                automation_sha,
            )
            self.assertEqual(
                prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha),
                mandant_sha,
            )

    def test_builds_update_matrix(self) -> None:
        """Bildet alle Mandantenbranches aus zentralen Zuordnungen und Rollout-Stufen.

        Das kartesische Produkt stellt sicher, dass jeder konfigurierte Mandant
        und jede Releaselinie über Entwicklungs-, Abnahme- und
        Bereitstellungsbranch aktualisiert wird.
        """

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
