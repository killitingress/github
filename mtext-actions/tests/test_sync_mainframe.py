"""Prüft die lokale Ressourcensynchronisation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError
from lbs_delivery.sync import publish_server_sync, sync_resources

from tests.support import git, load_test_configuration, setup_sync_repository


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt einen erreichbaren Entwicklungscommit und seine Konfiguration."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_sync_repository(self.root)
        self.configuration = load_test_configuration(self.repository)

    def test_sync_stages_complete_project_and_rejects_invalid_branch(self) -> None:
        """Prüft Staging, Ersetzung und die Branch-Zuordnung zur Zielstufe."""

        staging = self.root / "staging"
        result = sync_resources(
            self.configuration,
            repository_root=self.repository,
            commit=git(self.repository, "rev-parse", "HEAD"),
            source_branch="R261/Entwicklung",
            staging_root=staging,
            execute=False,
        )
        self.assertEqual(result["projects"], ["LOMS_Basis"])
        target = self.root / "serverSync"
        (target / "LOMS_Basis").mkdir(parents=True)
        (target / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")
        publish_server_sync(staging, target)
        self.assertEqual(
            (target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"),
            "new",
        )

        with self.assertRaises(DeliveryError):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="R261/Ungueltig",
                staging_root=self.root / "staging-invalid",
                execute=False,
            )


if __name__ == "__main__":
    unittest.main()
