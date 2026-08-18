"""Prüft die warnende Syntaxkontrolle für JSON- und XML-Ressourcen."""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.resource_check import run
from lbs_delivery.process import DeliveryError

from tests.support import AUTOMATION_ROOT, TempDirTestCase, git, init_git_repository

FORMATS_PATH = AUTOMATION_ROOT / "config/ressourcenformate.json"


class CheckResourcesTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = self.root / "source"
        self.repository.mkdir()

    def write(self, relative_path: str, content: str) -> None:
        path = self.repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_full_resource_check_contract(self) -> None:
        self.write("formular.formio", '{"components": [{"type": "textfield"}]}')
        self.write("brief.model", "<brief><absatz>Text</absatz></brief>")
        self.write("projekt/formular:a,b.formio", '{\n  "components": [\n}')
        self.write("projekt/brief.conf", "<brief>\n  <absatz>\n</brief>")
        self.write("hinweis.txt", "kein Prüfgegenstand")
        self.write(".git/interne-daten.json", "kein JSON")
        (self.repository / "verknuepfung.json").symlink_to(self.repository / ".git/interne-daten.json")
        summary = self.root / "summary.md"
        output = io.StringIO()

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), redirect_stdout(output):
            result = run(root=self.repository, formats_path=FORMATS_PATH, changed_only=False)

        command_output = output.getvalue()
        self.assertIn("::warning file=projekt/brief.conf,line=3,col=3", command_output)
        self.assertIn("::warning file=projekt/formular%3Aa%2Cb.formio,line=3,col=1", command_output)
        self.assertEqual(result, {"status": "RESOURCE_CHECKED", "files": 4, "warnings": 2})

        summary_text = summary.read_text(encoding="utf-8")
        self.assertIn("Geprüfte Dateien: 4", summary_text)
        self.assertIn("Warnungen: 2", summary_text)
        self.assertIn("blockieren den Pull Request nicht", summary_text)

    def test_pull_request_checks_changed_resources(self) -> None:
        init_git_repository(self.repository)
        self.write("bestehend.formio", '{"bewusst": NaN}')
        self.write("brief.datamodel", "<brief />")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "Ausgangsstand")
        self.write("brief.datamodel", "<brief>")
        self.write("notiz.txt", "kein Prüfgegenstand")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "Änderung")

        output = io.StringIO()
        with redirect_stdout(output):
            result = run(root=self.repository, formats_path=FORMATS_PATH, changed_only=True)

        command_output = output.getvalue()
        self.assertIn("::warning file=brief.datamodel", command_output)
        self.assertNotIn("bestehend.formio", command_output)
        self.assertEqual(result, {"status": "RESOURCE_CHECKED", "files": 1, "warnings": 1})

    def test_reports_resource_format_error(self) -> None:
        """Erhält die fachliche Meldung einer ungültigen Formatzuordnung."""

        formats = self.root / "formate.json"
        formats.write_text('{"dateiendungen": {".json": "json", ".JSON": "json"}}', encoding="utf-8")

        with self.assertRaisesRegex(DeliveryError, "Dateiendung mehrfach"):
            run(root=self.repository, formats_path=formats, changed_only=False)


if __name__ == "__main__":
    unittest.main()
