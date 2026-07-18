from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
EXPECTED = {"validate-config.yml", "sync-resources.yml", "release.yml"}


class WorkflowContractTests(unittest.TestCase):
    def test_thin_pinned_mandant_workflows(self) -> None:
        self.assertEqual({path.name for path in WORKFLOWS.glob("*.yml")}, EXPECTED)
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text()
            self.assertIn("permissions:\n  contents: read", text)
            self.assertNotIn("run:", text)
            matches = re.findall(
                r"uses: j520730/mtext-actions/.+@([0-9a-f]{40})", text
            )
            self.assertTrue(matches, path.name)
            for pin in matches:
                self.assertIn(f"automation_ref: {pin}", text)

        sync = (WORKFLOWS / "sync-resources.yml").read_text()
        self.assertIn("/Entwicklung", sync)
        self.assertIn("/Abnahme", sync)
        self.assertNotIn("/Bereitstellung", sync)

        release = (WORKFLOWS / "release.yml").read_text()
        self.assertIn("R[0-9][0-9][0-9].[0-9][0-9][0-9]", release)
        self.assertIn("serialize_publication: true", release)

        mandant = json.loads((ROOT / "config/mandant.json").read_text())["mandant"]
        self.assertEqual((mandant["code"], mandant["repository"]), ("FI", ROOT.name))


if __name__ == "__main__":
    unittest.main()
