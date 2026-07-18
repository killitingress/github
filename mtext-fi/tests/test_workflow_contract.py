from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


# Wurzel des Mandanten-Repositorys.
ROOT = Path(__file__).resolve().parents[1]
# Verzeichnis der dünnen Mandanten-Workflows.
WORKFLOWS = ROOT / ".github/workflows"
# Vollständiger erwarteter Workflowbestand des Mandanten.
EXPECTED = {"validate-config.yml", "sync-resources.yml", "release.yml"}


class WorkflowContractTests(unittest.TestCase):
    def test_thin_pinned_mandant_workflows(self) -> None:
        """Prüft Bestand, Pins und Leserechte der Mandanten-Workflows."""

        self.assertEqual({path.name for path in WORKFLOWS.glob("*.yml")}, EXPECTED)
        # Reguläre Ausdrücke prüfen die SHA-Bindung zentraler Workflow-Aufrufe.
        # Die Mandantenebene bleibt ein dünner, lesender Aufruf zentraler Workflows.
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text()
            self.assertIn("permissions:\n  contents: read", text)
            self.assertNotIn("run:", text)
            # Extrahiert die vollständige SHA aus einem zentralen Workflow-Aufruf.
            matches = re.findall(
                r"uses: j520730/mtext-actions/.+@([0-9a-f]{40})", text
            )
            self.assertTrue(matches, path.name)
            for pin in matches:
                self.assertIn(f"automation_ref: {pin}", text)

        # Automatische Synchronisation ist ausschließlich für Entwicklung und
        # Abnahme erlaubt.
        sync = (WORKFLOWS / "sync-resources.yml").read_text()
        self.assertIn("/Entwicklung", sync)
        self.assertIn("/Abnahme", sync)
        self.assertNotIn("/Bereitstellung", sync)

        release = (WORKFLOWS / "release.yml").read_text()
        self.assertIn("R[0-9][0-9][0-9].[0-9][0-9][0-9]", release)
        self.assertIn("serialize_publication: true", release)

        mandant = json.loads((ROOT / "config/mandant.json").read_text())["mandant"]
        self.assertEqual(
            (mandant["kuerzel"], mandant["repository"]), ("FI", ROOT.name)
        )


if __name__ == "__main__":
    unittest.main()
