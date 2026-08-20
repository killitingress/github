"""Prüft die Vorbereitung zentraler und mandantenseitiger Workflow-Aktualisierungen."""

from __future__ import annotations

import io
import json
import shutil
import unittest
from contextlib import redirect_stderr

from lbs_delivery.process import DeliveryError
from lbs_delivery.rollout import build_update_matrix, prepare_mandant_update, verify_automation

from tests.support import AUTOMATION_ROOT, TempDirTestCase, git, init_git_repository, ZERO_SHA

INDEPENDENT_WORKFLOW = """jobs:
  eigene-aktion:
    steps:
      - uses: beispiel/eigene-action@v1
        with:
          automation_ref: eigene-version
"""


def mandant_workflow(workflow: str, job: str) -> str:
    return f"""jobs:
  {job}:
    uses: FinanzInformatik/fi_lbs_entw_oms_mtext_actions/.github/workflows/{workflow}@{ZERO_SHA}
    with:
      automation_ref: {ZERO_SHA}
"""


class UpdateWorkflowsTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.automation_root = self.root / "automation"
        shutil.copytree(AUTOMATION_ROOT / ".github/workflows", self.automation_root / ".github/workflows")
        mandant_workflows = (self.root / "mandant/.github/workflows")
        mandant_workflows.mkdir(parents=True)
        self.mandant_workflow = mandant_workflows / "sync-resources.yml"
        self.mandant_workflow.write_text(mandant_workflow("reusable-sync-resources.yml", "sync"), encoding="utf-8")
        self.custom_workflow = mandant_workflows / "eigener-mtext-workflow.yaml"
        self.custom_workflow.write_text(mandant_workflow("reusable-check-resources.yml", "eigene-pruefung"), encoding="utf-8")
        self.independent_workflow = mandant_workflows / "eigener-workflow.yml"
        self.independent_workflow.write_text(INDEPENDENT_WORKFLOW, encoding="utf-8")
        self.mandant_root = self.root / "mandant"
        for repository in (self.automation_root, self.mandant_root):
            init_git_repository(repository)
            git(repository, "add", ".")
            git(repository, "commit", "-q", "-m", "Ausgangsstand")

    def test_rollout_preparation_and_verification(self) -> None:
        initial_sha = git(self.automation_root, "rev-parse", "HEAD")
        with self.assertRaisesRegex(DeliveryError, "angegebenen Commit"):
            verify_automation(self.automation_root, "1" * 40)

        with redirect_stderr(io.StringIO()):
            automation_sha = verify_automation(self.automation_root, initial_sha)
            mandant_sha = prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha)
        workflow = self.mandant_workflow.read_text(encoding="utf-8")
        self.assertEqual(workflow.count(automation_sha), 2)
        self.assertIn("sync:", workflow)
        self.assertEqual(self.custom_workflow.read_text(encoding="utf-8").count(automation_sha), 2)
        self.assertEqual(self.independent_workflow.read_text(encoding="utf-8"), INDEPENDENT_WORKFLOW)

        with redirect_stderr(io.StringIO()):
            self.assertEqual(verify_automation(self.automation_root, automation_sha), automation_sha)
            self.assertEqual(prepare_mandant_update(self.automation_root, self.mandant_root, automation_sha), mandant_sha)

    def test_builds_update_matrix(self) -> None:
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
                    "mtext_ziele": {"Entwicklung": "en", "Funktionstest": "fu"},
                    "releaselinien": {
                        "R261": {"etaps_linie": "01", "hostprofil": "FKT"},
                        "R270": {"etaps_linie": "02", "hostprofil": "JUR"},
                    },
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


if __name__ == "__main__":
    unittest.main()
