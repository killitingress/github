"""Prüft den Konfigurationsvertrag des Repositories ohne externe Systeme."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from sync_resources import build_parser as build_sync_parser
from validate_config import run as validate_config

from lbs_delivery.config import load_mandanten_zuordnung
from lbs_delivery.process import DeliveryError, Status, execute

from tests.support import load_test_configuration, setup_repository, write_mandant


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt ein gültiges Mandanten-Repository als Ausgangspunkt jedes Tests."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="main")

    def test_warns_on_project_deviation(self) -> None:
        """Meldet fehlende und zusätzliche Projekte als Warnung, nicht als Fehler."""

        (self.repository / "Fonts/value.txt").unlink()
        (self.repository / "Fonts").rmdir()
        (self.repository / "LOMS_Autonom").mkdir()
        configuration = load_test_configuration(self.repository)
        self.assertTrue(any("Projekte fehlen" in warnung for warnung in configuration.warnungen))
        self.assertTrue(any("zusätzlich" in warnung for warnung in configuration.warnungen))

    def test_derives_fragment_project_codes_for_by(self) -> None:
        """Leitet BY-Fragmentcodes aus Verzeichnisnamen ab."""

        for project in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_PKA"):
            (self.repository / project / "value.txt").unlink()
            (self.repository / project).rmdir()
        (self.repository / "LOMS_Basis").rename(self.repository / "LOMS_Basis[BY]")
        (self.repository / "LOMS_Autonom[BY]").mkdir()
        configuration = load_test_configuration(
            self.repository,
            mandant={"kuerzel": "BY"},
            repository_name="FinanzInformatik/fi_lbs_entw_oms_by",
        )
        self.assertEqual(configuration.projects, {"LOMS_Autonom[BY]": "AUTON", "LOMS_Basis[BY]": "BASIS"})
        self.assertEqual(configuration.subsystem, "BYMT")

    def test_rejects_invalid_configuration(self) -> None:
        """Lehnt widersprüchliche Identität, Zuordnung und Projektstruktur ab."""

        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"kuerzel": "BY"})
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, repository_name="FinanzInformatik/fi_lbs_entw_oms_unbekannt")
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"releaselinie": "R999"})

        mandanten_path = self.root / "mandanten.json"
        mandanten_path.write_text(
            json.dumps(
                {
                    "FI": {"repository": "FinanzInformatik/fi_lbs_entw_oms_fi", "subsystem": "LOMS"},
                    "BY": {"repository": "FinanzInformatik/fi_lbs_entw_oms_fi", "subsystem": "BYMT"},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(DeliveryError):
            load_mandanten_zuordnung(mandanten_path)

        (self.repository / "LOMS_Basisdaten").mkdir()
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository)

    def test_cli_keeps_runner_context_out_of_arguments(self) -> None:
        """Übergibt nur den Commit. Branch und Ereignis stammen aus dem Runner."""

        with self.subTest(validate_config=True):
            mandant_path = self.repository / ".github/config.json"
            mandant_path.parent.mkdir()
            write_mandant(mandant_path, kuerzel="BY")
            stderr = io.StringIO()
            with (
                patch.dict(
                    "os.environ",
                    {
                        "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                        "GITHUB_WORKSPACE": str(self.root),
                    },
                    clear=True,
                ),
                redirect_stdout(io.StringIO()),
                redirect_stderr(stderr),
            ):
                exit_code = execute(validate_config)
            self.assertEqual(exit_code, 2)
            self.assertIn(Status.VALIDATION_FAILED.value, stderr.getvalue())
            self.assertIn("Mandant passt nicht zum Repository", stderr.getvalue())

        with self.subTest(sync_resources=True):
            parser = build_sync_parser()
            sync = parser.parse_args(["--commit", "a" * 40])
            self.assertFalse(hasattr(sync, "source_branch"))
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(["--commit", "a" * 40, "--repository-root", "source"])


if __name__ == "__main__":
    unittest.main()
