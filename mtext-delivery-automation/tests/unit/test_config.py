from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


AUTOMATION_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = AUTOMATION_ROOT.parent


def load_json_compatible_yaml(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MandantConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (AUTOMATION_ROOT / "config/mandant.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.config = load_json_compatible_yaml(
            WORKSPACE_ROOT / "mtext-fi/config/mandant.yml"
        )
        cls.validator = Draft202012Validator(cls.schema)

    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def test_fi_config_matches_schema(self) -> None:
        self.validator.validate(self.config)

    def test_repository_identity_and_historical_fi_mapping(self) -> None:
        mandant = self.config["mandant"]
        self.assertEqual(mandant["repository"], f"mtext-{mandant['code'].lower()}")
        self.assertEqual(mandant["subsystem"], "LOMS")
        self.assertEqual(
            {project["name"]: project["package_code"] for project in mandant["projects"]},
            {
                "Configuration": "CONFI",
                "Fonts": "FONTS",
                "LOMS_Framework": "FRAME",
                "LOMS_Basis": "BASIS",
                "LOMS_PKA": "PKA",
            },
        )
        self.assertEqual(
            mandant["stages"],
            {
                "FKT": {"assignment": "LOMS000066", "level": "FKTE"},
                "JUR": {"assignment": "LOMS000067", "level": "JURP"},
            },
        )

    def test_project_names_paths_and_package_codes_are_unique(self) -> None:
        projects = self.config["mandant"]["projects"]
        for key in ("name", "source_path", "package_code"):
            values = [project[key] for project in projects]
            self.assertEqual(len(values), len(set(values)), key)

    def test_r251_fi_sync_exception_is_explicit_and_sync_only(self) -> None:
        self.assertEqual(
            self.config["mandant"]["sync_overrides"],
            [
                {
                    "release_line": "R251",
                    "environment": "Entwicklung",
                    "additional_projects": [
                        {
                            "name": "LOMS_Basis[FI]",
                            "source_path": "LOMS_Basis[FI]",
                            "sync_only": True,
                        }
                    ],
                }
            ],
        )

    def test_schema_rejects_unknown_keys_and_unknown_mandants(self) -> None:
        with_unknown_key = copy.deepcopy(self.config)
        with_unknown_key["mandant"]["credentials"] = "must-not-exist"
        with self.assertRaises(ValidationError):
            self.validator.validate(with_unknown_key)

        with_unknown_mandant = copy.deepcopy(self.config)
        with_unknown_mandant["mandant"]["code"] = "XX"
        with self.assertRaises(ValidationError):
            self.validator.validate(with_unknown_mandant)


class DeploymentConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_json_compatible_yaml(
            AUTOMATION_ROOT / "config/deployments.yml"
        )

    def test_only_inventory_backed_release_lines_are_configured(self) -> None:
        self.assertEqual(
            self.config["release_lines"],
            {
                "R251": {"line": "W", "stage": "JUR"},
                "R260": {"line": "X", "stage": "JUR"},
                "R261": {"line": "Y", "stage": "FKT"},
                "R270": {"line": "Z", "stage": "JUR"},
            },
        )
        self.assertNotIn("default", self.config["release_lines"])

    def test_branch_to_environment_mapping_is_unique_and_safe(self) -> None:
        environments = self.config["environments"]
        branches = [item["logical_branch"] for item in environments.values()]
        self.assertEqual(len(branches), len(set(branches)))
        self.assertTrue(environments["Entwicklung"]["deploy_on_push"])
        self.assertTrue(environments["Abnahme"]["deploy_on_push"])
        self.assertFalse(environments["Bereitstellung"]["deploy_on_push"])
        self.assertTrue(environments["Bereitstellung"]["release_on_tag"])

    def test_each_release_line_has_two_explicit_adapter_targets(self) -> None:
        release_line_codes = {
            item["line"] for item in self.config["release_lines"].values()
        }
        targets = self.config["adapter"]["targets"]
        self.assertEqual(set(targets), release_line_codes)
        for line, line_targets in targets.items():
            self.assertEqual(set(line_targets), {"entwicklung", "abnahme"})
            self.assertEqual(
                line_targets["entwicklung"],
                f"https://{line}A.fiv-mtext-do1.en4920.de",
            )
            self.assertEqual(
                line_targets["abnahme"],
                f"https://{line}A.fiv-mtext-do0.en4920.de",
            )

    def test_no_polling_and_no_mainframe_end_success_claim(self) -> None:
        self.assertFalse(self.config["adapter"]["polling"])
        self.assertFalse(self.config["mainframe"]["polling"])
        self.assertEqual(
            self.config["mainframe"]["success_status"], "MAINFRAME_SUBMITTED"
        )


if __name__ == "__main__":
    unittest.main()
