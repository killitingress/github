"""Prüft Mandantenkonfiguration und Projektverzeichnisse."""

from __future__ import annotations

import json
import unittest

from lbs_delivery.config import Configuration
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

    def test_derives_fragment_project_codes_for_by(self) -> None:
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
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"kuerzel": "BY"})
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, repository_name="FinanzInformatik/fi_lbs_entw_oms_unbekannt")
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"releaselinie": "999"})

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
            Configuration.load_mandanten_zuordnung(mandanten_path)

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
        with self.assertRaisesRegex(DeliveryError, "M/Text-Ziele"):
            Configuration.load_releaselinien_zuordnung(releaselinien_path)

        (self.repository / "LOMS_Basisdaten").mkdir()
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository)


if __name__ == "__main__":
    unittest.main()
