"""Prüft den Konfigurationsvertrag ohne externe Systeme."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status

from tests.support import (
    load_test_configuration,
    setup_repository,
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt ein temporäres Mandanten-Repository mit gültiger Basis."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Entwicklung")
        self.mandant_path = self.root / "mandant.json"

    def test_reference_project_deviation_only_warns(self) -> None:
        """Meldet fehlende und zusätzliche Projekte, ohne sie fachlich zu sperren."""

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

    def test_fragment_projects_remove_mandant_suffix_for_code(self) -> None:
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
            mandant={"kuerzel": "BY", "repository": "mtext-by"},
            repository_name="mtext-by",
        )
        self.assertEqual(
            configuration.projects,
            {"LOMS_Autonom[BY]": "AUTON", "LOMS_Basis[BY]": "BASIS"},
        )
        self.assertEqual(configuration.warnungen, ())

    def test_rejects_repository_name_mismatch(self) -> None:
        """Lehnt ab, wenn der Workflow ein anderes Repository nennt."""

        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={"repository": "mtext-by"},
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_rejects_duplicate_derived_project_code(self) -> None:
        """Lehnt zwei Projekte mit demselben Paket- und Membercode ab."""

        (self.repository / "LOMS_Basisdaten").mkdir()
        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
            )
        self.assertIn("Projektcodes", str(context.exception))

    def test_rejects_symlink_during_central_project_scan(self) -> None:
        """Prüft die einmalige Symlink-Regel beim Laden der Projektstruktur."""

        (self.repository / "LOMS_Basis/link.txt").symlink_to(
            self.repository / "Fonts/value.txt"
        )
        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
            )
        self.assertIn("Symlink", str(context.exception))

    def test_ignores_unused_mandant_fields(self) -> None:
        """Ignoriert zusätzliche Angaben im Mandanten und seinen Hostprofilen."""

        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
            mandant={
                "unbekannt": "Wert",
                "hostprofile": {
                    "FKT": {
                        "assignment": "LOMS000066",
                        "stage": "FKTE",
                        "unbekannt": "Wert",
                    },
                    "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
                },
            },
        )
        self.assertEqual(configuration.kuerzel, "FI")

    def test_ignores_unused_releaselinie_fields(self) -> None:
        """Ignoriert zusätzliche Angaben einer zentralen Releaselinie."""

        releaselinien = self.root / "releaselinien.json"
        releaselinien.write_text(
            json.dumps(
                {
                    "R261": {
                        "etaps_linie": "en01",
                        "hostprofil": "FKT",
                        "unbekannt": "Wert",
                    }
                }
            ),
            encoding="utf-8",
        )
        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
            releaselinien_path=releaselinien,
        )
        self.assertIn("R261", configuration.releaselinien)


if __name__ == "__main__":
    unittest.main()
