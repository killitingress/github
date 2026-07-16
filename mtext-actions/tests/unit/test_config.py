from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from lbs_delivery.config import (
    load_deployments_config,
    load_mandant_config,
    release_branch,
    resolve_adapter_url,
    validate_release_promotion,
    validate_release_tag,
)
from lbs_delivery.errors import DeliveryError, Status


ROOT = Path(__file__).resolve().parents[2]
MANDANT_CONFIG = ROOT / "tests/fixtures/mandant.json"
MANDANT_SCHEMA = ROOT / "config/mandant.schema.json"
DEPLOYMENTS_CONFIG = ROOT / "config/deployments.json"
DEPLOYMENTS_SCHEMA = ROOT / "config/deployments.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mandant_document = load_json(MANDANT_CONFIG)
        cls.mandant_schema = load_json(MANDANT_SCHEMA)
        cls.deployments_document = load_json(DEPLOYMENTS_CONFIG)
        cls.deployments_schema = load_json(DEPLOYMENTS_SCHEMA)
        cls.mandant = load_mandant_config(
            MANDANT_CONFIG, MANDANT_SCHEMA, repository_name="mtext-fi"
        )
        cls.deployments = load_deployments_config(
            DEPLOYMENTS_CONFIG, DEPLOYMENTS_SCHEMA
        )

    def test_schemas_and_example_documents_are_valid(self) -> None:
        for schema, document in (
            (self.mandant_schema, self.mandant_document),
            (self.deployments_schema, self.deployments_document),
        ):
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(document)

    def test_repository_identity_and_historical_fi_mapping(self) -> None:
        self.assertEqual(self.mandant["repository"], "mtext-fi")
        self.assertEqual(self.mandant["subsystem"], "LOMS")
        self.assertEqual(
            {
                project["name"]: project["package_code"]
                for project in self.mandant["projects"]
            },
            {
                "Configuration": "CONFI",
                "Fonts": "FONTS",
                "LOMS_Framework": "FRAME",
                "LOMS_Basis": "BASIS",
                "LOMS_PKA": "PKA",
            },
        )
        self.assertEqual(self.mandant["sync_overrides"], [])

    def test_schema_rejects_unknown_keys_and_unknown_mandants(self) -> None:
        with_unknown_key = copy.deepcopy(self.mandant_document)
        with_unknown_key["mandant"]["credentials"] = "must-not-exist"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.mandant_schema).validate(with_unknown_key)

        with_unknown_mandant = copy.deepcopy(self.mandant_document)
        with_unknown_mandant["mandant"]["code"] = "XX"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.mandant_schema).validate(with_unknown_mandant)

    def test_only_inventory_backed_release_lines_are_configured(self) -> None:
        self.assertEqual(
            self.deployments["release_lines"],
            {
                "R260": {"line": "en03", "stage": "JUR"},
                "R261": {"line": "en01", "stage": "FKT"},
                "R270": {"line": "en02", "stage": "JUR"},
            },
        )
        self.assertNotIn("default", self.deployments["release_lines"])

    def test_branch_and_adapter_mappings_are_explicit(self) -> None:
        environments = self.deployments["environments"]
        branches = [item["logical_branch"] for item in environments.values()]
        self.assertEqual(len(branches), len(set(branches)))
        self.assertTrue(environments["Entwicklung"]["deploy_on_push"])
        self.assertTrue(environments["Abnahme"]["deploy_on_push"])
        self.assertFalse(environments["Bereitstellung"]["deploy_on_push"])
        self.assertTrue(environments["Bereitstellung"]["release_on_tag"])
        self.assertEqual(
            resolve_adapter_url(self.deployments, "R261", "Entwicklung"),
            "https://en01e.ltoma.intern/vMtextAdapter/sync",
        )

    def test_only_runtime_parameters_are_configured(self) -> None:
        self.assertFalse(
            {"method", "content_type", "success_status_class", "polling"}
            & set(self.deployments["adapter"])
        )
        self.assertFalse(
            {"tag_pattern", "full_suffix", "delta_base_suffix"}
            & set(self.deployments["release"])
        )
        self.assertFalse(
            {"template", "polling", "success_status"}
            & set(self.deployments["mainframe"])
        )

    def test_tag_promotion_and_repository_guards(self) -> None:
        validate_release_tag(self.deployments, "R261.100")
        validate_release_tag(self.deployments, "R261.108")
        self.assertEqual(release_branch(self.deployments, "R261"), "R261/Bereitstellung")
        validate_release_promotion(
            self.deployments,
            "release/R261-20260715T143000Z",
            "R261/Bereitstellung",
        )
        with self.assertRaises(DeliveryError):
            validate_release_promotion(
                self.deployments, "R261/Abnahme", "R261/Bereitstellung"
            )
        with self.assertRaises(DeliveryError):
            validate_release_promotion(
                self.deployments,
                "feature/R261/12345-example",
                "R261/Entwicklung",
            )
        with self.assertRaisesRegex(
            DeliveryError,
            "source branch and release branch must use the same release line",
        ):
            validate_release_promotion(
                self.deployments,
                "release/R260-20260715T143000Z",
                "R261/Bereitstellung",
            )
        with self.assertRaises(DeliveryError):
            validate_release_tag(self.deployments, "R999.100")
        with self.assertRaises(DeliveryError) as raised:
            load_mandant_config(
                MANDANT_CONFIG, MANDANT_SCHEMA, repository_name="mtext-by"
            )
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

    def test_external_contracts_default_to_locked(self) -> None:
        self.assertFalse(self.deployments["adapter"]["contract_approved"])
        self.assertFalse(
            self.deployments["adapter"]["server_sync_contract_approved"]
        )
        self.assertFalse(self.deployments["mainframe"]["contract_approved"])


if __name__ == "__main__":
    unittest.main()
