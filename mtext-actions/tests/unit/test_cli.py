from __future__ import annotations

import argparse
import unittest
from unittest.mock import patch

from lbs_delivery import cli
from lbs_delivery.errors import DeliveryError, Status


class SyncCliTests(unittest.TestCase):
    def test_sync_rejects_inconsistent_branch_and_environment(self) -> None:
        """Prüft die Branchform und ihre Zuordnung zur Synchronisationsstage."""

        invalid_sources = (
            ("R261", "Entwicklung"),
            ("R261/Abnahme", "Entwicklung"),
            ("R261/Entwicklung", "Bereitstellung"),
            ("R999/Entwicklung", "Entwicklung"),
        )
        configs = (
            {"projects": []},
            {"R261": {"mtext_linie": "en01", "uebergabeprofil": "FKT"}},
        )
        for source_branch, environment in invalid_sources:
            with self.subTest(branch=source_branch, environment=environment):
                arguments = argparse.Namespace(
                    source_branch=source_branch,
                    environment=environment,
                )
                with patch.object(cli, "_load_configs", return_value=configs):
                    with self.assertRaises(DeliveryError) as raised:
                        cli._sync(arguments)
                self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)


if __name__ == "__main__":
    unittest.main()
