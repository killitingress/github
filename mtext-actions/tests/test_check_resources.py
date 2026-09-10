"""Prüft die warnende Syntaxkontrolle für JSON- und XML-Ressourcen."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import mtext
from lbs_delivery.process import Status
from lbs_delivery.resource_check import _NODE_COMMAND

from tests.support import TempDirTestCase, git, init_git_repository, load_test_configuration


class CheckResourcesTests(TempDirTestCase):
    def setUp(self) -> None:
        """Legt die Mandantenquelle im Workflow-Arbeitsbereich an."""

        super().setUp()
        self.repository = self.root / "source"
        self.repository.mkdir()
        for project_name in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_Basis", "LOMS_PKA"):
            (self.repository / project_name).mkdir()

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
        self.write("LOMS_Basis/formular.formio", '{\n  "components": [\n}')
        self.write("LOMS_Basis/brief.mapping", "<brief>\n  <absatz>\n</brief>")
        self.write("variante.pageLayouts", "<seite>")
        self.write("bruch.js", "const a = 1;\nfunction(\n")
        self.write("LOMS_Testdaten/ungueltig.xml", "")
        self.write("hinweis.txt", "kein Prüfgegenstand")
        self.write(".git/interne-daten.json", "kein JSON")
        (self.repository / "verknuepfung.json").symlink_to(self.repository / ".git/interne-daten.json")
        load_test_configuration(self.repository, mandant={"excluded_projects": ["LOMS_Testdaten"]})
        output = io.StringIO()

        with (
            patch.dict(os.environ, {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
            }),
            patch.object(sys, "argv", ["mtext.py", "resources", "check"]),
            redirect_stdout(output),
        ):
            result = mtext.run()

        command_output = output.getvalue()
        files = 8 if _NODE_COMMAND else 6
        warnings = 4 if _NODE_COMMAND else 3
        self.assertIn("::warning file=LOMS_Basis/brief.mapping,line=3,col=3", command_output)
        self.assertIn("::warning file=LOMS_Basis/formular.formio,line=3,col=1", command_output)
        self.assertIn("::warning file=variante.pageLayouts", command_output)
        self.assertNotIn("LOMS_Testdaten", command_output)
        self.assertNotIn("start.pageLayout", command_output)
        if _NODE_COMMAND:
            self.assertIn("::warning file=bruch.js,line=2,col=1", command_output)
            self.assertNotIn("aktion.js", command_output)
        else:
            self.assertNotIn("bruch.js", command_output)

        result.pop("summary")
        self.assertEqual(result, {"status": Status.RESOURCE_CHECKED, "files": files, "warnings": warnings})

    def test_pull_request_checks_changed_resources(self) -> None:
        """Prüft beim Pull Request die Ressourcen aus dem Git-Vergleich."""

        init_git_repository(self.repository)
        self.write("LOMS_Basis/platzhalter.txt", "Projektinhalt")
        self.write("LOMS_Testdaten/ignoriert.xml", "<test />")
        self.write("bestehend.formio", '{"bewusst": NaN}')
        self.write("brief.datamodel", "<brief />")
        load_test_configuration(self.repository, mandant={"excluded_projects": ["LOMS_Testdaten"]})
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "Ausgangsstand")
        self.write("brief.datamodel", "<brief>")
        self.write("LOMS_Testdaten/ignoriert.xml", "")
        self.write("notiz.txt", "kein Prüfgegenstand")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-q", "-m", "Änderung")

        output = io.StringIO()
        with (
            patch.dict(os.environ, {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
            }),
            patch.object(sys, "argv", ["mtext.py", "resources", "check"]),
            redirect_stdout(output),
        ):
            result = mtext.run()

        command_output = output.getvalue()
        self.assertIn("::warning file=brief.datamodel", command_output)
        self.assertNotIn("LOMS_Testdaten", command_output)
        self.assertNotIn("bestehend.formio", command_output)
        result.pop("summary")
        self.assertEqual(result, {"status": Status.RESOURCE_CHECKED, "files": 1, "warnings": 1})


if __name__ == "__main__":
    unittest.main()
