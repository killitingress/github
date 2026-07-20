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

    def test_loads_valid_configuration(self) -> None:
        """Akzeptiert Mandant, Hostprofile, Projekte und Releaselinien."""

        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
        )
        self.assertEqual(configuration.kuerzel, "FI")
        self.assertEqual(configuration.ispw, "P")
        self.assertEqual(
            configuration.projects,
            {
                "Configuration": "CONFI",
                "Fonts": "FONTS",
                "LOMS_Basis": "BASIS",
                "LOMS_Framework": "FRAME",
                "LOMS_PKA": "PKA",
            },
        )
        self.assertIn("R261", configuration.releaselinien)
        self.assertEqual(configuration.warnungen, ())

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

    def test_complete_reference_project_set_has_no_warning(self) -> None:
        """Bestätigt den aktuellen FI-Referenzstand ohne ihn vorzuschreiben."""

        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
        )
        self.assertEqual(
            configuration.projects,
            {
                "Configuration": "CONFI",
                "Fonts": "FONTS",
                "LOMS_Basis": "BASIS",
                "LOMS_Framework": "FRAME",
                "LOMS_PKA": "PKA",
            },
        )
        self.assertEqual(configuration.warnungen, ())

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

    def test_reference_repository_mandant_deviation_only_warns(self) -> None:
        """Meldet ein unplausibles Mandantenkürzel für ein bekanntes Repository."""

        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
            mandant={"repository": "mtext-by"},
            repository_name="mtext-by",
        )
        self.assertTrue(
            any("Mandantenkürzel" in warnung for warnung in configuration.warnungen)
        )

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

    def test_derives_project_code_from_new_project(self) -> None:
        """Leitet auch für ein neues Projekt den Paket- und Membercode ab."""

        (self.repository / "LOMS_Dokumente").mkdir()
        configuration = load_test_configuration(
            self.root,
            self.repository,
            mandant_path=self.mandant_path,
        )
        self.assertEqual(configuration.projects["LOMS_Dokumente"], "DOKUM")
        self.assertTrue(
            any("zusätzlich" in warnung for warnung in configuration.warnungen)
        )

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

    def test_rejects_invalid_ispw_instance(self) -> None:
        """Lehnt andere Werte als Test oder Produktion ab."""

        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={"ispw": "X"},
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_rejects_unknown_configuration_field(self) -> None:
        """Lehnt Felder außerhalb des versionierten Konfigurationsvertrags ab."""

        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={"unbekannt": "Wert"},
            )
        self.assertIn("unbekannte Felder", str(context.exception))

    def test_rejects_unknown_hostprofile_field(self) -> None:
        """Lehnt zusätzliche Felder innerhalb eines Hostprofils ab."""

        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={
                    "hostprofile": {
                        "FKT": {
                            "assignment": "LOMS000066",
                            "stage": "FKTE",
                            "unbekannt": "Wert",
                        },
                        "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
                    }
                },
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_rejects_unknown_releaselinie_field(self) -> None:
        """Lehnt zusätzliche Felder einer zentralen Releaselinie ab."""

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
        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                releaselinien_path=releaselinien,
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_rejects_invalid_hostprofile_stage(self) -> None:
        """Lehnt Hostprofile außerhalb der sechs CodePipeline-Stages ab."""

        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                mandant={
                    "hostprofile": {
                        "FKT": {"assignment": "LOMS000066", "stage": "INVALID"}
                    }
                },
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_rejects_releaselinie_without_hostprofile(self) -> None:
        """Lehnt Releaselinien ab, deren Hostprofil nicht existiert."""

        releaselinien = self.root / "releaselinien.json"
        releaselinien.write_text(
            json.dumps(
                {"R261": {"etaps_linie": "en01", "hostprofil": "MISSING"}}
            ),
            encoding="utf-8",
        )
        with self.assertRaises(DeliveryError) as context:
            load_test_configuration(
                self.root,
                self.repository,
                mandant_path=self.mandant_path,
                releaselinien_path=releaselinien,
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)


if __name__ == "__main__":
    unittest.main()
