"""Prüft den Konfigurationsvertrag des Repositories ohne externe Systeme.

Die Tests decken zentrale Identitätszuordnung, Projektermittlung,
Warnungsverhalten und die Kommandozeilenübersetzung von Validierungsfehlern ab.
"""

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

from lbs_delivery.config import _load_mandanten_zuordnung
from lbs_delivery.process import DeliveryError, Status, execute

from tests.support import (
    load_test_configuration,
    setup_repository,
    write_mandant,
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt ein gültiges Mandanten-Repository als Ausgangspunkt jedes Tests.

        Ein neuer temporärer Git-Bestand verhindert, dass Änderungen eines
        Prüffalls einen anderen beeinflussen.
        """

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Entwicklung")

    def test_warns_on_project_deviation(self) -> None:
        """Meldet Abweichungen im Projektbestand, ohne die Konfiguration abzulehnen.

        Der Referenzbestand dient der betrieblichen Sichtbarkeit. Fehlende und
        zusätzliche Projekte müssen deshalb Warnungen bleiben.
        """

        (self.repository / "Fonts/value.txt").unlink()
        (self.repository / "Fonts").rmdir()
        (self.repository / "LOMS_Autonom").mkdir()
        configuration = load_test_configuration(self.repository)
        self.assertTrue(any("Projekte fehlen" in warnung for warnung in configuration.warnungen))
        self.assertTrue(any("zusätzlich" in warnung for warnung in configuration.warnungen))

    def test_derives_fragment_project_codes_for_by(self) -> None:
        """Leitet die Projektcodes der BY-Fragmente aus ihren Verzeichnisnamen ab.

        Der Test belegt, dass Mandantensuffixe die externen Projektcodes für
        Paketnamen und Mainframe-Member nicht verändern.
        """

        for project in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_PKA"):
            (self.repository / project / "value.txt").unlink()
            (self.repository / project).rmdir()
        (self.repository / "LOMS_Basis").rename(self.repository / "LOMS_Basis[BY]")
        (self.repository / "LOMS_Autonom[BY]").mkdir()
        mandant = {"kuerzel": "BY"}
        configuration = load_test_configuration(self.repository, mandant=mandant, repository_name="<oms_team>/mtext-by")
        self.assertEqual(configuration.projects, {"LOMS_Autonom[BY]": "AUTON", "LOMS_Basis[BY]": "BASIS"})
        self.assertEqual(configuration.subsystem, "BYMT")

    def test_rejects_invalid_configuration(self) -> None:
        """Lehnt widersprüchliche Mandantenidentität, Zuordnungen und Projektstruktur ab.

        Diese Fälle betreffen dieselbe Vertrauensgrenze. Angaben aus dem
        Repository dürfen der zentralen Zuständigkeit nicht widersprechen.
        """

        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, mandant={"kuerzel": "BY"})

        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository, repository_name="<oms_team>/unbekannt")

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
            _load_mandanten_zuordnung(mandanten_path)

        (self.repository / "LOMS_Basisdaten").mkdir()
        with self.assertRaises(DeliveryError):
            load_test_configuration(self.repository)

    def test_validate_config_script_maps_validation_errors(self) -> None:
        """Ordnet Konfigurationsfehler dem dokumentierten Validierungs-Exitcode zu.

        Passt die Mandantenangabe nicht zum aufrufenden Repository, muss der
        Einstiegspunkt seinen stabilen Status und eine sichere Fehlermeldung
        ausgeben.
        """

        mandant_path = self.repository / ".github/config.json"
        mandant_path.parent.mkdir()
        write_mandant(mandant_path, kuerzel="BY")
        stderr = io.StringIO()
        environment = {"GITHUB_REPOSITORY": "<oms_team>/mtext-fi", "GITHUB_WORKSPACE": str(self.root)}
        with (
            patch.dict("os.environ", environment, clear=True),
            redirect_stdout(io.StringIO()),
            redirect_stderr(stderr),
        ):
            exit_code = execute(validate_config)
        self.assertEqual(exit_code, 2)
        self.assertIn(Status.VALIDATION_FAILED.value, stderr.getvalue())
        self.assertIn("Mandant passt nicht zum Repository", stderr.getvalue())

    def test_sync_script_contains_only_run_specific_arguments(self) -> None:
        """Hält Infrastrukturpfade und Repositoryidentität aus den Kommandozeilenoptionen heraus.

        Diese Werte stammen aus dem vertrauenswürdigen Runner-Kontext. Die
        Kommandozeile übergibt lediglich den Commit, der sich je Aufruf ändert.
        """

        parser = build_sync_parser()
        sync = parser.parse_args(["--commit", "a" * 40])
        self.assertFalse(hasattr(sync, "source_branch"))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--commit", "a" * 40, "--repository-root", "source"])


if __name__ == "__main__":
    unittest.main()
