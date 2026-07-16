from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
WORKFLOW_FILES = {
    "validate-config.yml",
    "sync-resources.yml",
    "release.yml",
}
PIN_PATTERN = re.compile(
    r"uses: ([a-zA-Z0-9.-]+)/mtext-actions/"
    r"\.github/workflows/(reusable-[a-z-]+\.yml)@([0-9a-f]{40})"
)


class WorkflowContractTests(unittest.TestCase):
    def test_expected_thin_workflows_exist(self) -> None:
        self.assertEqual(
            {path.name for path in WORKFLOWS.glob("*.yml")}, WORKFLOW_FILES
        )

    def test_reusable_workflows_are_pinned_to_full_commit_shas(self) -> None:
        for workflow_name in WORKFLOW_FILES:
            text = (WORKFLOWS / workflow_name).read_text(encoding="utf-8")
            matches = PIN_PATTERN.findall(text)
            self.assertTrue(matches, workflow_name)
            self.assertNotRegex(text, r"uses: .+@(main|master|HEAD)\s*$")
            for owner, _, pin in matches:
                self.assertEqual(owner, "j520730")
                self.assertRegex(pin, r"^[0-9a-f]{40}$")
                self.assertIn(f"automation_ref: {pin}", text)

    def test_workflows_are_thin_and_use_read_only_permissions(self) -> None:
        forbidden = ("run:", "curl ", "svn ", "ftp ", "password", "secret.")
        for workflow_name in WORKFLOW_FILES:
            text = (WORKFLOWS / workflow_name).read_text(encoding="utf-8")
            self.assertIn("permissions:\n  contents: read", text)
            for token in forbidden:
                self.assertNotIn(token, text.lower(), (workflow_name, token))

    def test_sync_workflow_has_only_two_explicit_target_environments(self) -> None:
        text = (WORKFLOWS / "sync-resources.yml").read_text(encoding="utf-8")
        self.assertIn("R[0-9][0-9][0-9]/Entwicklung", text)
        self.assertIn("R[0-9][0-9][0-9]/Abnahme", text)
        for release_line in ("R260", "R261", "R270"):
            self.assertNotIn(f"- {release_line}/", text)
        self.assertNotIn("type: choice", text)
        self.assertIn("endsWith(github.ref_name, '/Entwicklung')", text)
        self.assertIn("endsWith(github.ref_name, '/Abnahme')", text)
        self.assertNotIn("/Bereitstellung", text)
        self.assertNotIn("release_line: UNSET", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_config_validation_runs_only_for_config_pushes_without_write_path(self) -> None:
        text = (WORKFLOWS / "validate-config.yml").read_text(encoding="utf-8")
        self.assertIn("push:", text)
        self.assertIn("- '**'", text)
        self.assertIn("- config/mandant.json", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("--execute", text)
        self.assertIn("reusable-validate-config.yml", text)

    def test_release_workflow_uses_tag_contract(self) -> None:
        text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
        self.assertIn("R[0-9][0-9][0-9].[0-9][0-9][0-9]", text)
        self.assertNotIn("required_branch:", text)
        self.assertEqual(text.count("uses: j520730/mtext-actions/"), 1)
        self.assertNotIn("reusable-publish-mainframe.yml", text)
        self.assertIn("serialize_publication: true", text)
        self.assertNotIn("branches:", text)

    def test_mandant_configuration_matches_repository_identity(self) -> None:
        config = json.loads((ROOT / "config/mandant.json").read_text(encoding="utf-8"))
        self.assertEqual(config["mandant"]["code"], "FI")
        self.assertEqual(config["mandant"]["repository"], ROOT.name)


if __name__ == "__main__":
    unittest.main()
