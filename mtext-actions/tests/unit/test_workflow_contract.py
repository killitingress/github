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
REUSABLE = EXPECTED - {"ci.yml"}
ACTION_USE = re.compile(r"uses:\s+([^\s]+)")


class CentralWorkflowContractTests(unittest.TestCase):
    def test_expected_reusable_workflows_exist(self) -> None:
        self.assertEqual({path.name for path in WORKFLOWS.glob("*.yml")}, EXPECTED)

    def test_all_external_actions_are_commit_pinned(self) -> None:
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            for reference in ACTION_USE.findall(text):
                owner_and_path, separator, pin = reference.rpartition("@")
                self.assertTrue(separator, (path.name, reference))
                self.assertRegex(pin, r"^[0-9a-f]{40}$", (path.name, reference))
                self.assertNotIn("example-org", owner_and_path)

    def test_only_public_workflow_contracts_are_reusable(self) -> None:
        for workflow_name in REUSABLE:
            text = (WORKFLOWS / workflow_name).read_text(encoding="utf-8")
            self.assertIn("workflow_call:", text)
        self.assertNotIn(
            "workflow_call:", (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        )

    def test_workflows_reference_json_configuration(self) -> None:
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("deployments.yml", text)
            self.assertNotIn("mandant.yml", text)

    def test_publish_requires_environment_secrets_and_execute(self) -> None:
        text = (WORKFLOWS / "reusable-release.yml").read_text(encoding="utf-8")
        self.assertIn("needs: build", text)
        self.assertIn("environment: Bereitstellung", text)
        self.assertIn("secrets.MAINFRAME_FTP_PASSWORD", text)
        self.assertIn("--execute", text)

    def test_config_validation_has_no_external_write_path(self) -> None:
        text = (WORKFLOWS / "reusable-validate-config.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("validate-config", text)
        for token in ("--execute", "environment:", "secrets.", "MAINFRAME_"):
            self.assertNotIn(token, text)

    def test_release_uses_ghes_compatible_artifact_actions(self) -> None:
        text = (WORKFLOWS / "reusable-release.yml").read_text(encoding="utf-8")
        self.assertIn(
            "actions/upload-artifact@c6a3b2bd78b3985e4b2f15397fec357f0fd808de",
            text,
        )
        self.assertIn(
            "actions/download-artifact@ad191675b41f6a5b46da9a048cb6893812da158b",
            text,
        )

    def test_central_tests_have_their_own_ci_workflow(self) -> None:
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn("python }}\" -m unittest discover", text)


if __name__ == "__main__":
    unittest.main()
