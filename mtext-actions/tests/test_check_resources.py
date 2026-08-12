"""Prüft die warnende Syntaxkontrolle für JSON- und XML-Ressourcen."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from check_resources import main

# Die Tests verwenden die produktive Zuordnung als Eigentümer der unterstützten
# Dateiendungen.
ROOT = Path(__file__).resolve().parents[1]


class CheckResourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt einen eigenen Repositorybaum für jeden Test."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temporary_root = Path(self.temporary.name)
        self.root = self.temporary_root / "source"
        self.root.mkdir()
        self.formats_path = ROOT / "config/ressourcenformate.json"

    def write(self, relative_path: str, content: str) -> None:
        """Schreibt eine Testressource einschließlich benötigter Verzeichnisse."""

        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_git(self, *arguments: str) -> str:
        """Führt eine erwartbar erfolgreiche Git-Operation im Testbaum aus."""

        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_full_resource_check_contract(self) -> None:
        """Prüft Auswahl, Syntaxbefunde und nicht blockierende GitHub-Ausgaben."""

        self.write("formular.formio", '{"components": [{"type": "textfield"}]}')
        self.write("brief.model", '<brief><absatz>Text</absatz></brief>')
        self.write("projekt/formular:a,b.formio", '{\n  "components": [\n}')
        self.write("projekt/brief.conf", "<brief>\n  <absatz>\n</brief>")
        self.write("hinweis.txt", "kein Prüfgegenstand")
        self.write(".git/interne-daten.json", "kein JSON")
        (self.root / "verknuepfung.json").symlink_to(
            self.root / ".git/interne-daten.json"
        )
        summary = self.root / "summary.md"
        output = io.StringIO()

        with (
            patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}),
            redirect_stdout(output),
        ):
            result = main(
                ["--root", str(self.root), "--formats", str(self.formats_path)]
            )

        self.assertEqual(result, 0)
        command_output = output.getvalue()
        self.assertIn(
            "::warning file=projekt/brief.conf,line=3,col=3",
            command_output,
        )
        self.assertIn(
            "::warning file=projekt/formular%3Aa%2Cb.formio,line=3,col=1",
            command_output,
        )
        self.assertIn('"status":"RESOURCE_CHECKED"', command_output)
        self.assertIn('"files":4', command_output)
        self.assertIn('"warnings":2', command_output)

        summary_text = summary.read_text(encoding="utf-8")
        self.assertIn("Geprüfte Dateien: 4", summary_text)
        self.assertIn("Warnungen: 2", summary_text)
        self.assertIn("blockieren den Pull Request nicht", summary_text)

    def test_pull_request_checks_changed_resources(self) -> None:
        """Prüft im Pull Request ausschließlich neue und geänderte Ressourcen."""

        self.run_git("init", "-q")
        self.run_git("config", "user.name", "Test")
        self.run_git("config", "user.email", "test@example.invalid")
        self.write("bestehend.formio", '{"bewusst": NaN}')
        self.write("brief.datamodel", "<brief />")
        self.run_git("add", ".")
        self.run_git("commit", "-q", "-m", "Ausgangsstand")

        self.write("brief.datamodel", "<brief>")
        self.write("notiz.txt", "kein Prüfgegenstand")
        self.run_git("add", ".")
        self.run_git("commit", "-q", "-m", "Änderung")

        output = io.StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "--root",
                    str(self.root),
                    "--formats",
                    str(self.formats_path),
                    "--changed-only",
                ]
            )

        self.assertEqual(result, 0)
        self.assertIn("::warning file=brief.datamodel", output.getvalue())
        self.assertNotIn("bestehend.formio", output.getvalue())
        self.assertIn('"files":1', output.getvalue())
        self.assertIn('"warnings":1', output.getvalue())


if __name__ == "__main__":
    unittest.main()
