"""Prüft die Sicherheitsgrenzen der wiederverwendbaren Workflows."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from workflow_configuration import CONFIGURATION_WORKFLOW


# Diese Wurzel enthält Code, Templates und zentrale Workflows des Neubaus.
ROOT = Path(__file__).resolve().parents[1]
# Diese Dateien bilden die vollständige zentrale Workflowoberfläche.
EXPECTED_WORKFLOWS = {
    "ci.yml",
    CONFIGURATION_WORKFLOW,
    "reusable-validate-config.yml",
    "reusable-sync-resources.yml",
    "reusable-release.yml",
}


class WorkflowTests(unittest.TestCase):
    def test_workflows_keep_pins_and_external_boundaries(self) -> None:
        """Prüft Action-Pins, Freigabe, Secrets und explizite Ausführung."""

        workflows = ROOT / ".github/workflows"
        self.assertEqual(
            {path.name for path in workflows.glob("*.yml")}, EXPECTED_WORKFLOWS
        )
        runner_values: set[str] = set()
        for path in workflows.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            # Reguläre Ausdrücke prüfen Runnerfelder und feste Action-Pins.
            # Erkennt den fest eingetragenen Runnerwert jedes Jobs.
            workflow_runners = re.findall(r"(?m)^\s*runs-on:\s*(.+?)\s*$", text)
            self.assertTrue(workflow_runners, path)
            if path.name == CONFIGURATION_WORKFLOW:
                self.assertEqual(workflow_runners, ["${{ vars.FI_RUNNER_LABEL }}"])
            else:
                runner_values.update(workflow_runners)
            # Verhindert ein vom Aufrufer beeinflussbares Runnerfeld.
            self.assertNotRegex(text, r"(?m)^\s+runner_label:\s*")
            # Erkennt jede Action-Referenz bis zum nächsten Leerzeichen.
            references = re.findall(r"uses:\s+([^\s]+)", text)
            for reference in references:
                # Prüft den Pin auf eine vollständige kleingeschriebene SHA.
                self.assertRegex(reference.rpartition("@")[2], r"^[0-9a-f]{40}$")

        self.assertEqual(len(runner_values), 1)
        runner_value = next(iter(runner_values))
        self.assertNotIn("self-hosted", runner_value)
        self.assertNotIn("${{", runner_value)

        configuration = (workflows / CONFIGURATION_WORKFLOW).read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", configuration)
        self.assertNotRegex(configuration, r"(?m)^\s+(?:push|pull_request):")
        self.assertIn("environment: Einrichtung", configuration)
        self.assertIn("secrets.WORKFLOW_CONFIGURATION_TOKEN", configuration)
        self.assertIn("permissions:\n  contents: read", configuration)
        self.assertNotIn("run: mandant/", configuration)
        self.assertNotRegex(configuration, r"(?m)^\s+apply:")
        self.assertEqual(configuration.count("-m workflow_configuration"), 1)
        self.assertNotIn("git -C automation commit", configuration)
        self.assertNotIn("git -C mandant commit", configuration)

        release = (workflows / "reusable-release.yml").read_text(encoding="utf-8")
        self.assertIn("environment: Bereitstellung", release)
        self.assertIn("secrets.MAINFRAME_FTP_PASSWORD", release)
        self.assertIn("--execute", release)
        for name in (
            "reusable-validate-config.yml",
            "reusable-sync-resources.yml",
            "reusable-release.yml",
        ):
            workflow = (workflows / name).read_text(encoding="utf-8")
            self.assertIn("repository: j520730/mtext-actions", workflow)
            # Verhindert eine vom Mandanten wählbare Quelle der zentralen Automation.
            self.assertNotRegex(workflow, r"(?m)^\s+automation_repository:\s*")
            self.assertNotIn("--mandant-config", workflow)

        validation = (workflows / "reusable-validate-config.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--execute", validation)
        self.assertNotIn("secrets.", validation)


if __name__ == "__main__":
    unittest.main()
