"""Prüft die warnende Syntaxkontrolle für JSON- und XML-Ressourcen."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import mtext
from lbs_delivery.resource_check import _NODE_COMMAND

from tests.support import TempDirTestCase, git, init_git_repository


class CheckResourcesTests(TempDirTestCase):
    def setUp(self) -> None:
        """Legt die Mandantenquelle im Workflow-Arbeitsbereich an."""

        super().setUp()
        self.repository = self.root / "source"
        self.repository.mkdir()

    def write(self, relative_path: str, content: str) -> None:
        """Schreibt eine Ressource unterhalb der Mandantenquelle."""

        path = self.repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_full_resource_check(self) -> None:
        """Prüft die Ressourcen beim manuellen Workflow-Start."""

        self.write("formular.formio", '{"components": [{"type": "textfield"}]}')
        self.write("brief.model", "<brief><absatz>Text</absatz></brief>")
        self.write("start.pageLayout", "<seite />")
        self.write("aktion.js", "const x = 1;\n")
        self.write("projekt/formular:a,b.formio", '{\n  "components": [\n}')
        self.write("projekt/brief.mapping", "<brief>\n  <absatz>\n</brief>")
        self.write("variante.pageLayouts", "<seite>")
        self.write("bruch.js", "const a = 1;\nfunction(\n")
        self.write("hinweis.txt", "kein Prüfgegenstand")
        self.write(".git/interne-daten.json", "kein JSON")
        (self.repository / "verknuepfung.json").symlink_to(self.repository / ".git/interne-daten.json")
        summary = self.root / "summary.md"
        output = io.StringIO()

        with (
            patch.dict(os.environ, {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_STEP_SUMMARY": str(summary),
                "GITHUB_EVENT_NAME": "workflow_dispatch",
            }),
            patch.object(sys, "argv", ["mtext.py", "resources", "check"]),
            redirect_stdout(output),
        ):
            result = mtext.run()

        command_output = output.getvalue()
        files = 8 if _NODE_COMMAND else 6
        warnings = 4 if _NODE_COMMAND else 3
        self.assertIn("::warning file=projekt/brief.mapping,line=3,col=3", command_output)
        self.assertIn("::warning file=projekt/formular%3Aa%2Cb.formio,line=3,col=1", command_output)
        self.assertIn("::warning file=variante.pageLayouts", command_output)
        self.assertNotIn("start.pageLayout", command_output)
        if _NODE_COMMAND:
            self.assertIn("::warning file=bruch.js,line=2,col=1", command_output)
            self.assertNotIn("aktion.js", command_output)
        else:
            self.assertNotIn("bruch.js", command_output)
        self.assertEqual(result, {"status": "RESOURCE_CHECKED", "files": files, "warnings": warnings})

        summary_text = summary.read_text(encoding="utf-8")
        self.assertIn(f"Geprüfte Dateien: {files}", summary_text)
        self.assertIn(f"Warnungen: {warnings}", summary_text)
        self.assertIn("blockieren den Pull Request nicht", summary_text)
        if _NODE_COMMAND:
            self.assertIn("JavaScript-Prüfung: aktiv", summary_text)
        else:
            self.assertIn("JavaScript-Prüfung: übersprungen, Node.js nicht verfügbar", summary_text)

    def test_pull_request_checks_changed_resources(self) -> None:
        """Prüft beim Pull Request die Ressourcen aus dem Git-Vergleich."""

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
        with (
            patch.dict(os.environ, {"GITHUB_WORKSPACE": str(self.root), "GITHUB_EVENT_NAME": "pull_request"}),
            patch.object(sys, "argv", ["mtext.py", "resources", "check"]),
            redirect_stdout(output),
        ):
            result = mtext.run()

        command_output = output.getvalue()
        self.assertIn("::warning file=brief.datamodel", command_output)
        self.assertNotIn("bestehend.formio", command_output)
        self.assertEqual(result, {"status": "RESOURCE_CHECKED", "files": 1, "warnings": 1})


if __name__ == "__main__":
    unittest.main()
