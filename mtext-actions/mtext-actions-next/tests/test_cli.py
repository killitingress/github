"""Prüft die CLI-Ausgabe und dokumentierte Exitcodes."""

from __future__ import annotations

import io
import json
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
        self.mandant_path = self.root / "mandant.json"
        write_mandant(self.mandant_path)
        self.releaselinien = RELEASELINIEN
        self.common = [
            "--repository-root",
            str(self.repository),
            "--mandant-config",
            str(self.mandant_path),
            "--releaselinien",
            str(self.releaselinien),
            "--repository-name",
            "mtext-fi",
        ]

    def _run(self, *arguments: str) -> tuple[int, str, str]:
        """Führt main aus und sammelt Exitcode sowie stdout und stderr."""

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(list(arguments))
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_validate_config_prints_json_result(self) -> None:
        """Gibt CONFIG_VALIDATED als sortiertes JSON auf stdout aus."""

        exit_code, stdout, stderr = self._run("validate-config", *self.common)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assertEqual(result["status"], Status.CONFIG_VALIDATED.value)
        self.assertEqual(result["mandanten_kuerzel"], "FI")
        self.assertIn("R261", result["releaselinien"])

    def test_validate_config_returns_validation_exit_code(self) -> None:
        """Übersetzt Konfigurationsfehler in Exitcode 2."""

        write_mandant(self.mandant_path, repository="mtext-by")
        exit_code, _stdout, stderr = self._run("validate-config", *self.common)
        self.assertEqual(exit_code, 2)
        self.assertIn(Status.VALIDATION_FAILED.value, stderr)

    def test_build_release_returns_source_exit_code_for_wrong_sha(self) -> None:
        """Übersetzt einen falschen Trigger-SHA in Exitcode 3."""

        git(self.repository, "tag", "R261.100")
        git(
            self.repository,
            "update-ref",
            "refs/remotes/origin/R261/Bereitstellung",
            "HEAD",
        )
        git(self.repository, "checkout", "--detach", "R261.100")
        exit_code, _stdout, stderr = self._run(
            "build-release",
            *self.common,
            "--tag",
            "R261.100",
            "--trigger-sha",
            "0" * 40,
            "--output",
            str(self.root / "dist"),
        )
        self.assertEqual(exit_code, 3)
        self.assertIn(Status.SOURCE_FAILED.value, stderr)
        self.assertIn("auslösender Commit", stderr)


if __name__ == "__main__":
    unittest.main()
