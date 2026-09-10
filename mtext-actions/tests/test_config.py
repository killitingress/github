"""Prüft Mandantenkonfiguration und Projektverzeichnisse."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from lbs_delivery.process import DeliveryError

from tests.support import TempDirTestCase, git, init_repository, load_test_configuration


class ConfigTests(TempDirTestCase):
    def setUp(self) -> None:
        """Bereitet ein Mandanten-Repository mit FI-Referenzprojekten vor."""

        super().setUp()
        # Mandanten-Repository mit den hinterlegten FI-Referenzprojekten erzeugen.
        self.repository = init_repository(self.root, branch="main")
        for project_name in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_Basis", "LOMS_PKA"):
            project = self.repository / project_name
            project.mkdir()
            (project / "value.txt").write_text("content\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "init")

    def test_validates_configuration_and_derives_fragment_projects(self) -> None:
        """Prüft ungültige Konfigurationen und die Zuordnung gültiger Fragmentprojekte."""

        # Derselbe Projektausschluss gilt für Projektableitung und enthaltene Ressourcen
        excluded_project = self.repository / "LOMS_Testdaten"
        excluded_project.mkdir()
        configuration = load_test_configuration(
            self.repository,
            mandant={"excluded_projects": [excluded_project.name]},
        )
        self.assertNotIn(excluded_project.name, configuration.projects)
        excluded_resource = excluded_project.relative_to(self.repository) / "daten.xml"
        self.assertTrue(configuration.excludes_project_path(excluded_resource))
        excluded_project.rmdir()

        # Mandant, Repository und Releaselinie müssen zusammenpassen
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"kuerzel": "BY"})
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, repository="FinanzInformatik/fi_lbs_entw_oms_unbekannt")
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"releaselinie": "999"})

        # zentrale Zuordnungen verlangen eindeutige Repositories und beide Umgebungsarten
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
        with patch("lbs_delivery.config.MANDANTEN_ZUORDNUNG_PATH", mandanten_path):
            with self.assertRaisesRegex(DeliveryError, "Mandantenzuordnung ist nicht eindeutig"):
                load_test_configuration(self.repository)

        releaselinien_path = self.root / "releaselinien.json"
        releaselinien_path.write_text(
            json.dumps(
                {
                    "mtext_ziele": {"Entwicklung": "en"},
                    "releaselinien": {"270": {"etaps_linie": "02", "hostprofil": "JUR"}},
                }
            ),
            encoding="utf-8",
        )
        with patch("lbs_delivery.config.RELEASELINIEN_ZUORDNUNG_PATH", releaselinien_path):
            with self.assertRaisesRegex(DeliveryError, "M/Text-Umgebungsarten"):
                load_test_configuration(self.repository)

        # LOMS_Basis und LOMS_Basisdaten ergeben beide BASIS und damit denselben Archivnamen
        colliding_project = self.repository / "LOMS_Basisdaten"
        colliding_project.mkdir()
        with self.assertRaisesRegex(DeliveryError, "Projektcodes sind nicht eindeutig"):
            load_test_configuration(self.repository)
        colliding_project.rmdir()

        # gültige Fragmentprojekte erhalten Projektcodes und das Mainframe-Subsystem des Mandanten
        for project in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_PKA"):
            (self.repository / project / "value.txt").unlink()
            (self.repository / project).rmdir()
        (self.repository / "LOMS_Basis").rename(self.repository / "LOMS_Basis[BY]")
        (self.repository / "LOMS_Autonom[BY]").mkdir()
        configuration = load_test_configuration(
            self.repository,
            mandant={"kuerzel": "BY"},
            repository="FinanzInformatik/fi_lbs_entw_oms_by",
        )
        self.assertEqual(configuration.projects, {"LOMS_Autonom[BY]": "AUTON", "LOMS_Basis[BY]": "BASIS"})
        self.assertEqual(configuration.subsystem, "BYMT")


if __name__ == "__main__":
    unittest.main()
