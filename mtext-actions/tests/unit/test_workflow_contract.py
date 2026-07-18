from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
EXPECTED = {
    "ci.yml",
    "reusable-validate-config.yml",
    "reusable-sync-resources.yml",
    "reusable-release.yml",
}


class CentralWorkflowContractTests(unittest.TestCase):
    def test_central_workflow_security_contract(self) -> None:
        self.assertEqual({path.name for path in WORKFLOWS.glob("*.yml")}, EXPECTED)
        for path in WORKFLOWS.glob("*.yml"):
            for reference in re.findall(r"uses:\s+([^\s]+)", path.read_text()):
                self.assertRegex(reference.rpartition("@")[2], r"^[0-9a-f]{40}$")

        release = (WORKFLOWS / "reusable-release.yml").read_text()
        self.assertIn("environment: Bereitstellung", release)
        self.assertIn("secrets.MAINFRAME_FTP_PASSWORD", release)
        self.assertIn("--execute", release)
        self.assertIn("actions/upload-artifact@c6a3b2bd78b3985e4b2f15397fec357f0fd808de", release)
        self.assertIn(
            "actions/download-artifact@ad191675b41f6a5b46da9a048cb6893812da158b",
            release,
        )

        validation = (WORKFLOWS / "reusable-validate-config.yml").read_text()
        self.assertNotIn("--execute", validation)
        self.assertNotIn("secrets.", validation)


if __name__ == "__main__":
    unittest.main()
