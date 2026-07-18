"""Prüft die Sicherheitsgrenzen der wiederverwendbaren Workflows."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


# Diese Wurzel enthält Code, Templates und zentrale Workflows des Neubaus.
ROOT = Path(__file__).resolve().parents[1]
# Die vier Dateien bilden die vollständige öffentliche Workflowoberfläche.
EXPECTED_WORKFLOWS = {
    "ci.yml",
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
        for path in workflows.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            # Reguläre Ausdrücke für unveränderlich gebundene Actions.
            # Erkennt jede Action-Referenz bis zum nächsten Leerzeichen.
            references = re.findall(r"uses:\s+([^\s]+)", text)
            # Prüft jeden Pin auf eine vollständige kleingeschriebene SHA.
            for reference in references:
                self.assertRegex(reference.rpartition("@")[2], r"^[0-9a-f]{40}$")

        release = (workflows / "reusable-release.yml").read_text(encoding="utf-8")
        self.assertIn("environment: Bereitstellung", release)
        self.assertIn("secrets.MAINFRAME_FTP_PASSWORD", release)
        self.assertIn("--execute", release)
        validation = (workflows / "reusable-validate-config.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--execute", validation)
        self.assertNotIn("secrets.", validation)


if __name__ == "__main__":
    unittest.main()

