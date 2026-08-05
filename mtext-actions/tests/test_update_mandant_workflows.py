"""Prüft die Vorbereitung abgestimmter zentraler und mandantenseitiger Workflow-Aktualisierungen.

Temporäre Git-Repositories prüfen Commit-Grenzen, einheitliche Revisionsbindungen,
Wiederholbarkeit und Abdeckung der Rollout-Matrix, ohne echte Repositories zu
verändern.
"""

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


# Der Testaufbau kopiert die zentralen Workflows aus dem geprüften Automations-Checkout.
ROOT = Path(__file__).resolve().parents[1]


class UpdateWorkflowsTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt getrennte temporäre Automations- und Mandanten-Repositories.

        Unabhängige Historien bilden die tatsächliche Rollout-Grenze ab. Die
        Tests können damit prüfen, welches Repository den jeweiligen Commit erhält.
        """

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.automation_root = self.root / "automation"
        shutil.copytree(ROOT / ".github/workflows", self.automation_root / ".github/workflows")
        for path in (self.automation_root / ".github/workflows").glob("*.yml"):
            workflow = path.read_text(encoding="utf-8").replace(RUNNER_PLACEHOLDER, "fi-runner")
            path.write_text(workflow, encoding="utf-8")

        self.mandant_root = self.root / "mandant"
        mandant_workflows = self.mandant_root / ".github/workflows"
        mandant_workflows.mkdir(parents=True)
        self.mandant_workflow = mandant_workflows / "sync-resources.yml"
        self.mandant_workflow.write_text(
            """jobs:
  sync-entwicklung:
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
        """Führt eine erwartbar erfolgreiche Git-Operation mit hilfreicher Diagnose aus.

        Die Test-Assertion statt `check=True` nimmt stderr in die reguläre
        unittest-Fehlermeldung auf, wenn die Testhistorie nicht wie vorgesehen
        aufgebaut wurde.
        """

        command = ["git", "-C", str(repository), *arguments]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_prepares_verified_workflow_updates_idempotently(self) -> None:
        """Prüft freigegebene Rollout-SHA, Mandantenbindung und Wiederholbarkeit.

        Eine abweichende zentrale SHA muss vor jeder Änderung scheitern.
        Erfolgreiche Wiederholungen behalten denselben Mandanten-Commit.
        """

        initial_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "angegebenen Commit"):
            verify_automation(self.automation_root, "1" * 40)

        with redirect_stderr(io.StringIO()):
            automation_sha = verify_automation(self.automation_root, initial_sha)
            mandant_sha = prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha)
        self.assertEqual(automation_sha, initial_sha)
        self.assertEqual(self.mandant_workflow.read_text(encoding="utf-8").count(automation_sha), 2)

        with redirect_stderr(io.StringIO()):
            self.assertEqual(verify_automation(self.automation_root, automation_sha), automation_sha)
            self.assertEqual(
                prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha),
                mandant_sha,
            )

    def test_builds_update_matrix(self) -> None:
        """Bildet die geschützten Mandantenbranches aus den zentralen Zuordnungen.

        Das kartesische Produkt stellt sicher, dass jeder konfigurierte Mandant
        `main` und die möglichen Release-Branches erhält. Feature-Branches sind
        kein eigenes Rollout-Ziel.
        """

        mandanten = self.root / "mandanten.json"
        mandanten.write_text(
            json.dumps(
                {
                    "FI": {
                        "repository": "<oms_team>/mtext-fi",
                        "subsystem": "LOMS",
                    },
                    "BY": {
                        "repository": "<oms_team>/mtext-by",
                        "subsystem": "BYMT",
                    },
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
            {
                "repository": "<oms_team>/mtext-fi",
                "kuerzel": "FI",
                "branch": "release/R261",
            },
            matrix,
        )
        self.assertIn(
            {
                "repository": "<oms_team>/mtext-by",
                "kuerzel": "BY",
                "branch": "main",
            },
            matrix,
        )

    def test_rejects_unconfigured_central_runner(self) -> None:
        """Prüft Runnerfelder, ohne harmlose Kommentare als Konfiguration zu lesen."""

        workflow = self.automation_root / ".github/workflows/ci.yml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8") + f"\n# {RUNNER_PLACEHOLDER}\n",
            encoding="utf-8",
        )
        automation_sha = self.run_git(self.automation_root, "rev-parse", "HEAD")
        self.assertEqual(verify_automation(self.automation_root, automation_sha), automation_sha)

        workflow.write_text(
            workflow.read_text(encoding="utf-8") + f"\nruns-on: {RUNNER_PLACEHOLDER}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Runner-Kennzeichen"):
            verify_automation(self.automation_root, automation_sha)

    def test_checks_target_branches_through_github_api(self) -> None:
        """Kodiert Branchpfade und unterscheidet fehlende Release-Branches von main."""

        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"ref":"refs/heads/release/R261"}'
        with patch("workflow_configuration.urllib.request.urlopen", return_value=response) as urlopen:
            self.assertTrue(
                check_target_branch("https://api.github.test", "team/mandant", "release/R261", "token")
            )
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.github.test/repos/team/mandant/git/ref/heads/release%2FR261",
        )

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

    def test_accepts_existing_update_pull_request(self) -> None:
        """Behandelt den bereits vorhandenen technischen Pull Request als Wiederanlauf."""

        existing = HTTPError(
            "https://api.github.test",
            422,
            "Unprocessable Entity",
            None,
            io.BytesIO(
                json.dumps(
                    {"errors": [{"message": "A pull request already exists for team:update"}]}
                ).encode("utf-8")
            ),
        )
        with patch("workflow_configuration.urllib.request.urlopen", side_effect=existing) as urlopen:
            open_update_pull_request(
                "https://api.github.test",
                "team/mandant",
                "release/R261",
                "mtext-actions/workflow-release-R261",
                "token",
            )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data)["base"], "release/R261")


if __name__ == "__main__":
    unittest.main()
