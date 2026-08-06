"""Prüft die Vorbereitung abgestimmter zentraler und mandantenseitiger Workflow-Aktualisierungen."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch

from workflow_configuration import (
    RUNNER_PLACEHOLDER,
    build_update_matrix,
    check_target_branch,
    open_update_pull_request,
    prepare_mandant_update,
    verify_automation,
)

ROOT = Path(__file__).resolve().parents[1]


class UpdateWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt getrennte temporäre CI/CD- und Mandanten-Repositories."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automation_root = self.root / "automation"
        shutil.copytree(ROOT / ".github/workflows", self.automation_root / ".github/workflows")
        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            path.write_text(path.read_text(encoding="utf-8").replace(RUNNER_PLACEHOLDER, "fi-runner"), encoding="utf-8")

        self.mandant_root = self.root / "mandant"
        mandant_workflows = self.mandant_root / ".github/workflows"
        mandant_workflows.mkdir(parents=True)
        self.mandant_workflow = mandant_workflows / "sync-resources.yml"
        self.mandant_workflow.write_text(
            """jobs:
  sync:
    uses: FinanzInformatik/fi_lbs_entw_oms_mtext_actions/.github/workflows/reusable-sync-resources.yml@0000000000000000000000000000000000000000
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
        """Führt eine erwartbar erfolgreiche Git-Operation mit hilfreicher Diagnose aus."""

        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_rollout_preparation_and_verification(self) -> None:
        """Prüft SHA, Runnerkennzeichen, Mandantenbindung und Wiederholbarkeit."""

        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "angegebenen Commit"):
            verify_automation(self.automation_root, "1" * 40)

        with redirect_stderr(io.StringIO()):
            automation_sha = verify_automation(self.automation_root, initial_sha)
            mandant_sha = prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha)
        workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.assertEqual(workflow.count(automation_sha), 2)
        self.assertIn("sync:", workflow)

        with redirect_stderr(io.StringIO()):
            self.assertEqual(verify_automation(self.automation_root, automation_sha), automation_sha)
            self.assertEqual(
                prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha),
                mandant_sha,
            )

        workflow_path = self.automation_root / ".github/workflows/ci.yml"
        with self.subTest(runner_im_kommentar=True):
            workflow_path.write_text(
                workflow_path.read_text(encoding="utf-8") + f"\n# {RUNNER_PLACEHOLDER}\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_automation(self.automation_root, automation_sha), automation_sha)

        with self.subTest(runner_im_job=True):
            workflow_path.write_text(
                workflow_path.read_text(encoding="utf-8") + f"\nruns-on: {RUNNER_PLACEHOLDER}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Runner-Kennzeichen"):
                verify_automation(self.automation_root, automation_sha)

    def test_builds_update_matrix(self) -> None:
        """Bildet main und mögliche Release-Branches für jeden Mandanten."""

        mandanten = self.root / "mandanten.json"
        mandanten.write_text(
            json.dumps(
                {
                    "FI": {"repository": "FinanzInformatik/fi_lbs_entw_oms_fi", "subsystem": "LOMS"},
                    "BY": {"repository": "FinanzInformatik/fi_lbs_entw_oms_by", "subsystem": "BYMT"},
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
        self.assertEqual(len(matrix), 6)
        self.assertIn(
            {"repository": "FinanzInformatik/fi_lbs_entw_oms_fi", "kuerzel": "FI", "branch": "release/R261"},
            matrix,
        )
        self.assertIn(
            {"repository": "FinanzInformatik/fi_lbs_entw_oms_by", "kuerzel": "BY", "branch": "main"},
            matrix,
        )

    def test_github_api_for_rollout(self) -> None:
        """Prüft Zielbranch und vorhandenen Pull Request über die GitHub-API."""

        with self.subTest(vorhandener_release_branch=True):
            response = MagicMock()
            response.__enter__.return_value = response
            response.status = 200
            response.read.return_value = b'{"ref":"refs/heads/release/R261"}'
            with patch("workflow_configuration.urllib.request.urlopen", return_value=response) as urlopen:
                self.assertTrue(
                    check_target_branch("https://api.github.test", "team/mandant", "release/R261", "token")
                )
            self.assertEqual(
                urlopen.call_args.args[0].full_url,
                "https://api.github.test/repos/team/mandant/git/ref/heads/release%2FR261",
            )

        with self.subTest(fehlender_release_branch=True):
            missing = HTTPError(
                "https://api.github.test",
                404,
                "Not Found",
                None,
                io.BytesIO(b'{"message":"Not Found"}'),
            )
            with patch("workflow_configuration.urllib.request.urlopen", side_effect=missing):
                self.assertFalse(
                    check_target_branch("https://api.github.test", "team/mandant", "release/R261", "token")
                )

        with self.subTest(fehlender_main_branch=True):
            missing_main = HTTPError(
                "https://api.github.test",
                404,
                "Not Found",
                None,
                io.BytesIO(b'{"message":"Not Found"}'),
            )
            with (
                patch("workflow_configuration.urllib.request.urlopen", side_effect=missing_main),
                self.assertRaisesRegex(RuntimeError, "HTTP 404"),
            ):
                check_target_branch("https://api.github.test", "team/mandant", "main", "token")

        with self.subTest(vorhandener_pull_request=True):
            existing = HTTPError(
                "https://api.github.test",
                422,
                "Unprocessable Entity",
                None,
                io.BytesIO(
                    json.dumps({"errors": [{"message": "A pull request already exists for team:update"}]}).encode(
                        "utf-8"
                    )
                ),
            )
            lookup = MagicMock()
            lookup.__enter__.return_value = lookup
            lookup.status = 200
            lookup.read.return_value = b'[{"number":42}]'
            with patch(
                "workflow_configuration.urllib.request.urlopen",
                side_effect=(existing, lookup),
            ) as urlopen:
                open_update_pull_request(
                    "https://api.github.test",
                    "team/mandant",
                    "release/R261",
                    "mtext_actions/workflow-release-R261",
                    "token",
                )
            create_request = urlopen.call_args_list[0].args[0]
            self.assertEqual(create_request.method, "POST")
            self.assertEqual(json.loads(create_request.data)["base"], "release/R261")
            lookup_request = urlopen.call_args_list[1].args[0]
            self.assertIn("head=team%3Amtext_actions%2Fworkflow-release-R261", lookup_request.full_url)


if __name__ == "__main__":
    unittest.main()
