"""Prüft den Konfigurationsvertrag ohne externe Systeme."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lbs_delivery.cli import main
from lbs_delivery.errors import DeliveryError, Status

from tests.support import (
    MANDANTEN,
    RELEASELINIEN,
    load_test_configuration,
    setup_repository,
    write_mandant,
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt ein temporäres Mandanten-Repository mit gültiger Basis."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Entwicklung")
        self.mandant_path = self.root / "mandant.json"

    def test_warns_on_project_deviation(self) -> None:
        """Meldet fehlende und zusätzliche Projekte ohne fachliche Sperre."""

        (self.repository / "Fonts/value.txt").unlink()
        (self.repository / "Fonts").rmdir()
        (self.repository / "LOMS_Autonom").mkdir()
        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
        )
        self.assertTrue(
            any("Projekte fehlen" in warnung for warnung in configuration.warnungen)
        )
        self.assertTrue(
            any("zusätzlich" in warnung for warnung in configuration.warnungen)
        )

    def test_derives_fragment_project_codes_for_by(self) -> None:
        """Leitet Projektcodes der BY-Fragmente aus ihren fachlichen Namen ab."""

        for project in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_PKA"):
            (self.repository / project / "value.txt").unlink()
            (self.repository / project).rmdir()
        (self.repository / "LOMS_Basis").rename(
            self.repository / "LOMS_Basis[BY]"
        )
        (self.repository / "LOMS_Autonom[BY]").mkdir()
        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
            mandant={"kuerzel": "BY"},
            repository_name="<oms_team>/mtext-by",
        )
        self.assertEqual(
            configuration.projects,
            {"LOMS_Autonom[BY]": "AUTON", "LOMS_Basis[BY]": "BASIS"},
        )
        self.assertEqual(configuration.subsystem, "BYMT")

    def test_rejects_invalid_configuration(self) -> None:
        """Lehnt ungültige Mandanten-, Zuordnungs- und Projektstruktur ab."""

        with self.assertRaises(DeliveryError):
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={"kuerzel": "BY"},
            )

        with self.assertRaises(DeliveryError):
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                repository_name="<oms_team>/unbekannt",
            )

        mandanten_path = self.root / "mandanten.json"
        mandanten_path.write_text(
            json.dumps(
                {
                    "FI": {
                        "repository": "<oms_team>/mtext-fi",
                        "subsystem": "LOMS",
                    },
                    "BY": {
                        "repository": "<oms_team>/mtext-fi",
                        "subsystem": "BYMT",
                    },
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(DeliveryError):
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandanten_path=mandanten_path,
            )

        (self.repository / "LOMS_Basisdaten").mkdir()
        with self.assertRaises(DeliveryError):
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
            )

        (self.repository / "LOMS_Basisdaten").rmdir()
        (self.repository / "LOMS_Basis/link.txt").symlink_to(
            self.repository / "Fonts/value.txt"
        )
        with self.assertRaises(DeliveryError):
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
            )

    def test_validate_config_cli_maps_validation_errors(self) -> None:
        """Übersetzt Konfigurationsfehler in Exitcode 2."""

        mandant_path = self.repository / ".github/config.json"
        mandant_path.parent.mkdir()
        write_mandant(mandant_path, kuerzel="BY")
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            exit_code = main(
                [
                    "validate-config",
                    "--repository-root",
                    str(self.repository),
                    "--releaselinien",
                    str(RELEASELINIEN),
                    "--mandanten",
                    str(MANDANTEN),
                    "--repository-name",
                    "<oms_team>/mtext-fi",
                ]
            )
        self.assertEqual(exit_code, 2)
        self.assertIn(Status.VALIDATION_FAILED.value, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
