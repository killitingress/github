"""Prüft lokales Staging und die serverSync-Ersetzung der Ressourcenlieferung.

Externe Adapter- und Zielpfade werden bei Bedarf abgegrenzt. Echte
Verzeichnisbäume prüfen dabei das Synchronisationsverhalten.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.sync import publish_server_sync, sync_resources

from tests.support import git, load_test_configuration, setup_sync_repository


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt einen gültigen Entwicklungscommit mit seiner Lieferkonfiguration.

        Die passende Remote-Referenz erfüllt dieselbe Abstammungsprüfung wie der
        produktive Synchronisationsworkflow.
        """

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_sync_repository(self.root)
        self.configuration = load_test_configuration(self.repository)

    def test_sync_stages_complete_project_and_rejects_invalid_branch(self) -> None:
        """Prüft vollständiges Staging, Ersetzung und Zuordnung von Branch zu Zielstufe.

        Der erfolgreiche Ablauf belegt, dass Projektinhalte serverSync und den
        Adapteraufruf erreichen. Der ungültige Branch zeigt, dass keine Umgebung
        außerhalb des vereinbarten Quellnamens gewählt werden kann.
        """

        staging = self.root / "staging"
        with (
            patch("lbs_delivery.sync.publish_server_sync") as publish,
            patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter,
        ):
            result = sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="R261/Entwicklung",
                staging_root=staging,
            )
        self.assertEqual(result["status"], Status.ADAPTER_ACCEPTED.value)
        publish.assert_called_once()
        adapter.assert_called_once()
        self.assertEqual((staging / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")
        target = self.root / "serverSync"
        (target / "LOMS_Basis").mkdir(parents=True)
        (target / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")
        publish_server_sync(staging, target)
        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")

        with self.assertRaises(DeliveryError):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="R261/Ungueltig",
                staging_root=self.root / "staging-invalid",
            )


if __name__ == "__main__":
    unittest.main()
