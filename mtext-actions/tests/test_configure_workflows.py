"""Prüft die idempotente Finalisierung der Workflowdateien."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


# Diese Wurzel enthält das Einrichtungskommando und die zentralen Workflowvorlagen.
ROOT = Path(__file__).resolve().parents[1]
# Das Kommando läuft wie bei der tatsächlichen Einrichtung als eigener Prozess.
SCRIPT = ROOT / "scripts/configure-workflows.py"
# Diese Testversion ist ein gültiger Commit und kein technischer Nullwert.
AUTOMATION_SHA = "1" * 40


class ConfigureWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt getrennte zentrale und mandantenseitige Workflowverzeichnisse."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automation_root = self.root / "mtext-actions"
        shutil.copytree(
            ROOT / ".github/workflows",
            self.automation_root / ".github/workflows",
        )
        self.mandant_root = self.root / "mtext-fi"
        mandant_workflows = self.mandant_root / ".github/workflows"
        mandant_workflows.mkdir(parents=True)
        self.mandant_workflow = mandant_workflows / "sync-resources.yml"
        self.mandant_workflow.write_text(
            """jobs:
  sync-entwicklung:
    uses: j520730/mtext-actions/.github/workflows/reusable-sync-resources.yml@0000000000000000000000000000000000000000
    with:
      automation_ref: 0000000000000000000000000000000000000000
  sync-abnahme:
    uses: j520730/mtext-actions/.github/workflows/reusable-sync-resources.yml@0000000000000000000000000000000000000000
    with:
      automation_ref: 0000000000000000000000000000000000000000
""",
            encoding="utf-8",
        )

    def run_script(
        self,
        *extra: str,
        automation_sha: str = AUTOMATION_SHA,
        runner_label: str = "fi-runner",
    ) -> subprocess.CompletedProcess[str]:
        """Startet Plan oder Anwendung mit den temporären Repositorypfaden."""

        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--automation-sha",
                automation_sha,
                "--runner-label",
                runner_label,
                "--automation-root",
                str(self.automation_root),
                "--mandant-root",
                str(self.mandant_root),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_plan_does_not_change_files(self) -> None:
        """Listet Änderungen, ohne die technischen Platzhalter zu ersetzen."""

        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PLANNED")
        self.assertEqual(report["pin_mismatches"], [])
        workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.assertIn("0" * 40, workflow)

    def test_apply_is_idempotent(self) -> None:
        """Schreibt beide Pins und den Runner genau einmal in alle Workflowdateien."""

        applied = self.run_script("--apply")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(json.loads(applied.stdout)["changed_files"])
        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8")
            self.assertNotIn("FI_RUNNER_LABEL_TO_BE_SET", workflow)
            self.assertIn('runs-on: "fi-runner"', workflow)
        release_workflow = (
            self.automation_root / ".github/workflows/reusable-release.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(release_workflow.count('runs-on: "fi-runner"'), 2)
        mandant_workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.assertEqual(mandant_workflow.count(AUTOMATION_SHA), 4)

        repeated = self.run_script("--apply")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["changed_files"], [])

    def test_reports_different_workflow_and_code_pins(self) -> None:
        """Weist eine bestehende Abweichung beider technischen Referenzen aus."""

        workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.mandant_workflow.write_text(
            workflow.replace(
                "automation_ref: " + "0" * 40,
                "automation_ref: " + "2" * 40,
                1,
            ),
            encoding="utf-8",
        )

        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["pin_mismatches"],
            [str(self.mandant_workflow)],
        )

    def test_ignores_different_pins_across_jobs(self) -> None:
        """Meldet nur abweichende Paare innerhalb desselben Jobs, nicht zwischen Jobs."""

        self.mandant_workflow.write_text(
            f"""jobs:
  sync-entwicklung:
    uses: j520730/mtext-actions/.github/workflows/reusable-sync-resources.yml@{"1" * 40}
    with:
      automation_ref: {"1" * 40}
  sync-abnahme:
    uses: j520730/mtext-actions/.github/workflows/reusable-sync-resources.yml@{"2" * 40}
    with:
      automation_ref: {"2" * 40}
""",
            encoding="utf-8",
        )

        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["pin_mismatches"], [])

    def test_invalid_mandant_workflow_prevents_all_writes(self) -> None:
        """Validiert den gesamten Dateisatz vor dem ersten Schreibzugriff."""

        broken = self.mandant_root / ".github/workflows/broken.yml"
        broken.write_text("jobs: {}\n", encoding="utf-8")

        result = self.run_script("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("Workflowreferenzen fehlen", result.stderr)
        central = (
            self.automation_root / ".github/workflows/reusable-release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("FI_RUNNER_LABEL_TO_BE_SET", central)

    def test_rejects_null_sha(self) -> None:
        """Verhindert die Aktivierung mit dem technischen Versionsplatzhalter."""

        result = self.run_script(automation_sha="0" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Nullwert", result.stderr)

    def test_rejects_runner_placeholder(self) -> None:
        """Verhindert die Aktivierung ohne bestätigtes FI-Runner-Kennzeichen."""

        result = self.run_script(runner_label="FI_RUNNER_LABEL_TO_BE_SET")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runner-label", result.stderr)


if __name__ == "__main__":
    unittest.main()
