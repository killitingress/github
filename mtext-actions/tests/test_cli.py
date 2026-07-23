"""Prüft die CLI-Übersetzung fachlicher Fehler in Exitcodes."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lbs_delivery.cli import main
from lbs_delivery.errors import Status

from tests.support import RELEASELINIEN, git, setup_repository, write_mandant


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt Mandant, Repository und gemeinsame CLI-Argumente."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Entwicklung")
        self.mandant_path = self.repository / ".github/config.json"
        self.mandant_path.parent.mkdir()
        write_mandant(self.mandant_path)
        git(self.repository, "add", ".github/config.json")
        git(self.repository, "commit", "-m", "config")
        self.common = [
            "--repository-root",
            str(self.repository),
            "--releaselinien",
            str(RELEASELINIEN),
            "--repository-name",
            "mtext-fi",
        ]

    def test_validate_config_returns_validation_exit_code(self) -> None:
        """Übersetzt Konfigurationsfehler in Exitcode 2."""

        write_mandant(self.mandant_path, repository="mtext-by")
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            exit_code = main(["validate-config", *self.common])
        self.assertEqual(exit_code, 2)
        self.assertIn(Status.VALIDATION_FAILED.value, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
