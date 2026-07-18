from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.config import load_mandant_config, load_releaselinien
from lbs_delivery.errors import DeliveryError, Status


# Wurzel des zentralen Automationsprojekts mit den Konfigurations-Fixtures.
ROOT = Path(__file__).resolve().parents[2]


class ReleaselinienConfigTests(unittest.TestCase):
    def test_releaselinie_values_are_owned_by_the_mapping(self) -> None:
        """Akzeptiert frei benannte M/Text-Linien und Übergabeprofile als Strings."""

        document = {
            "R261": {
                "mtext_linie": "fachlich-festgelegt",
                "uebergabeprofil": "eigenes-profil",
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releaselinien.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(load_releaselinien(path), document)

    def test_releaselinie_requires_string_values(self) -> None:
        """Lehnt typfremde M/Text-Linien und Übergabeprofilnamen ab."""

        invalid_values = (
            ("mtext_linie", None),
            ("mtext_linie", 261),
            ("uebergabeprofil", None),
            ("uebergabeprofil", 261),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "releaselinien.json"
            for field, invalid_value in invalid_values:
                with self.subTest(field=field, value=invalid_value):
                    releaselinie = {
                        "mtext_linie": "en01",
                        "uebergabeprofil": "FKT",
                    }
                    releaselinie[field] = invalid_value
                    path.write_text(
                        json.dumps({"R261": releaselinie}), encoding="utf-8"
                    )
                    with self.assertRaises(DeliveryError) as raised:
                        load_releaselinien(path)
                    self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

    def test_hostprofil_requires_codepipeline_stage(self) -> None:
        """Lehnt Hostprofile außerhalb der sechs erlaubten Stages ab."""

        config = json.loads(
            (ROOT / "tests/fixtures/mandant.json").read_text(encoding="utf-8")
        )
        config["mandant"]["hostprofile"]["FKT"]["stage"] = "DEV"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mandant.json"
            (Path(directory) / "LOMS_Basis").mkdir()
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(DeliveryError) as raised:
                load_mandant_config(
                    path,
                    repository_name="mtext-fi",
                    repository_root=directory,
                )
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

    def test_projects_are_visible_root_directories_except_exclusions(self) -> None:
        """Ermittelt Projekte aus der Wurzel und beachtet versteckte Elemente."""

        config = json.loads(
            (ROOT / "tests/fixtures/mandant.json").read_text(encoding="utf-8")
        )
        config["mandant"]["excluded_projects"] = ["LOMS_Testdaten"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("LOMS_Basis", "Fonts", "LOMS_Testdaten", ".github"):
                (root / name).mkdir()
            path = root / ".config.json"
            path.write_text(json.dumps(config), encoding="utf-8")

            mandant = load_mandant_config(
                path,
                repository_name="mtext-fi",
                repository_root=root,
            )

        self.assertEqual(mandant["projects"], ["Fonts", "LOMS_Basis"])


if __name__ == "__main__":
    unittest.main()
