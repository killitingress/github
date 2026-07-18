from __future__ import annotations

import re
import unittest
from pathlib import Path


# Wurzel des zentralen Automationsprojekts.
ROOT = Path(__file__).resolve().parents[2]
# Verzeichnis der zentralen wiederverwendbaren Workflows.
WORKFLOWS = ROOT / ".github/workflows"
# Vollständiger erwarteter Workflowbestand des zentralen Projekts.
EXPECTED = {
    "ci.yml",
    "reusable-validate-config.yml",
    "reusable-sync-resources.yml",
    "reusable-release.yml",
}


class CentralWorkflowContractTests(unittest.TestCase):
    def test_central_workflow_security_contract(self) -> None:
        """Prüft Bestand, Action-Pins und Sicherheitsgrenzen zentraler Workflows."""

        self.assertEqual({path.name for path in WORKFLOWS.glob("*.yml")}, EXPECTED)
        # Reguläre Ausdrücke prüfen die unveränderliche Bindung externer Actions.
        # Externe Actions bleiben durch vollständige SHAs unveränderlich gebunden.
        for path in WORKFLOWS.glob("*.yml"):
            # Erkennt jede verwendete Action-Referenz bis zum nächsten Leerzeichen.
            for reference in re.findall(r"uses:\s+([^\s]+)", path.read_text()):
                # Prüft den Pin nach `@` auf eine vollständige kleingeschriebene SHA.
                self.assertRegex(reference.rpartition("@")[2], r"^[0-9a-f]{40}$")

        # Nur der Release-Workflow darf Freigabe, Secrets und Übergabe enthalten.
        release = (WORKFLOWS / "reusable-release.yml").read_text()
        self.assertIn("environment: Bereitstellung", release)
        self.assertIn("secrets.MAINFRAME_FTP_PASSWORD", release)
        self.assertIn("--execute", release)
        self.assertIn(
            "actions/upload-artifact@c6a3b2bd78b3985e4b2f15397fec357f0fd808de",
            release,
        )
        self.assertIn(
            "actions/download-artifact@ad191675b41f6a5b46da9a048cb6893812da158b",
            release,
        )

        validation = (WORKFLOWS / "reusable-validate-config.yml").read_text()
        self.assertNotIn("--execute", validation)
        self.assertNotIn("secrets.", validation)


if __name__ == "__main__":
    unittest.main()
