"""Prüft lokales Staging und die serverSync-Ersetzung der Ressourcenlieferung.

Externe Adapter- und Zielpfade werden bei Bedarf abgegrenzt. Echte
Verzeichnisbäume prüfen dabei das Synchronisationsverhalten.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.git import resolve_sync_branch
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.sync import publish_full_server_sync, sync_resources

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

    def test_resolves_hierarchical_feature_branch(self) -> None:
        """Erhält die Releaselinie auch bei tiefer gegliederten Feature-Namen."""

        self.assertEqual(resolve_sync_branch("feature/R271/brief/anschreiben", "R270"), ("R271", True))
        with self.assertRaises(DeliveryError):
            resolve_sync_branch("feature/R271/", "R270")

    def test_sync_targets_complete_project_and_rejects_invalid_branch(self) -> None:
        """Prüft vollständiges Staging, Ersetzung und Zuordnung von Branch zu M/Text-Ziel.

        Der erfolgreiche Ablauf belegt, dass Projektinhalte serverSync und den
        Adapteraufruf erreichen. Der ungültige Branch zeigt, dass keine Umgebung
        außerhalb des vereinbarten Quellnamens gewählt werden kann.
        """

        staging = self.root / "staging"
        target = self.root / "serverSync"
        with (
            patch("lbs_delivery.sync.publish_full_server_sync") as publish,
            patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter,
        ):
            result = sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="feature/R261/test-sync",
                staging_root=staging,
                server_sync_root=target,
            )
        self.assertEqual(result["status"], Status.ADAPTER_ACCEPTED.value)
        publish.assert_called_once()
        adapter.assert_called_once_with(
            "https://en01e.ltoma.intern/vMtextAdapter/sync",
            timeout=30.0,
        )
        self.assertEqual((staging / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")
        (target / "LOMS_Basis").mkdir(parents=True)
        (target / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")
        publish_full_server_sync(staging, target)
        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")

        with self.assertRaises(DeliveryError):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="unbekannt",
                staging_root=self.root / "staging-invalid",
                server_sync_root=target,
            )

    def test_uses_successful_commit_for_incremental_server_sync(self) -> None:
        """Überträgt nach dem ersten Vollstand nur die Git-Änderungen zum neuen Commit.

        Der erfolgreiche Commit im dauerhaften Marker ist die Vergleichsbasis.
        Eine unveränderte Datei behält deshalb ihren Ziel-Zeitstempel, während
        geänderte, neue und gelöschte Ressourcen nachgeführt werden.
        """

        project = self.repository / "LOMS_Basis"
        unchanged = project / "unchanged.txt"
        unchanged.write_text("same", encoding="utf-8")
        (project / "deleted.txt").write_text("delete", encoding="utf-8")
        (project / "rename-old.txt").write_text("rename", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "add unchanged resource")
        git(self.repository, "update-ref", "refs/remotes/origin/feature/R261/test-sync", "HEAD")

        target = self.root / "persistent-serverSync"
        first_commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=first_commit,
                source_branch="feature/R261/test-sync",
                staging_root=self.root / "first-staging",
                server_sync_root=target,
            )
        unchanged_mtime = (target / "LOMS_Basis/unchanged.txt").stat().st_mtime_ns

        (project / "value.txt").write_text("changed", encoding="utf-8")
        (project / "new.txt").write_text("new", encoding="utf-8")
        (project / "deleted.txt").unlink()
        git(self.repository, "mv", "LOMS_Basis/rename-old.txt", "LOMS_Basis/rename-new.txt")
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-m", "change resources")
        git(self.repository, "update-ref", "refs/remotes/origin/feature/R261/test-sync", "HEAD")
        second_commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=second_commit,
                source_branch="feature/R261/test-sync",
                staging_root=self.root / "second-staging",
                server_sync_root=target,
            )

        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "changed")
        self.assertEqual((target / "LOMS_Basis/new.txt").read_text(encoding="utf-8"), "new")
        self.assertFalse((target / "LOMS_Basis/deleted.txt").exists())
        self.assertFalse((target / "LOMS_Basis/rename-old.txt").exists())
        self.assertEqual((target / "LOMS_Basis/rename-new.txt").read_text(encoding="utf-8"), "rename")
        self.assertEqual((target / "LOMS_Basis/unchanged.txt").stat().st_mtime_ns, unchanged_mtime)
        self.assertFalse((self.root / "second-staging/LOMS_Basis/unchanged.txt").exists())
        self.assertTrue((self.root / "second-staging/LOMS_Basis/value.txt").is_file())
        marker = json.loads((target / ".mtext-sync/FI.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["commit"], second_commit)

    def test_full_sync_replaces_project_despite_existing_marker(self) -> None:
        """Erzwingt mit vorhandenem Marker einen vollständigen Projektwechsel.

        Eine nicht im Repository enthaltene Zieldatei verschwindet nur beim
        Vollstand. Der Test grenzt `full_sync=True` damit vom normalen
        inkrementellen Lauf ab.
        """

        target = self.root / "full-serverSync"
        commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                source_branch="feature/R261/test-sync",
                staging_root=self.root / "initial-full-staging",
                server_sync_root=target,
            )
        (target / "LOMS_Basis/stale.txt").write_text("stale", encoding="utf-8")

        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                source_branch="feature/R261/test-sync",
                staging_root=self.root / "forced-full-staging",
                full_sync=True,
                server_sync_root=target,
            )

        self.assertFalse((target / "LOMS_Basis/stale.txt").exists())
        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")

    def test_rejects_invalid_server_sync_marker(self) -> None:
        """Lehnt beschädigte und einem anderen Repository gehörende Marker ab."""

        commit = git(self.repository, "rev-parse", "HEAD")
        marker_values = (
            "kein JSON",
            json.dumps({"repository": "anderes/repository", "commit": commit}),
        )
        for index, marker_value in enumerate(marker_values):
            with self.subTest(marker=index):
                target = self.root / f"invalid-marker-{index}"
                marker = target / ".mtext-sync/FI.json"
                marker.parent.mkdir(parents=True)
                marker.write_text(marker_value, encoding="utf-8")
                with self.assertRaisesRegex(DeliveryError, "Synchronisationsstand ist ungültig"):
                    sync_resources(
                        self.configuration,
                        repository_root=self.repository,
                        commit=commit,
                        source_branch="feature/R261/test-sync",
                        staging_root=self.root / f"invalid-marker-staging-{index}",
                        server_sync_root=target,
                    )

    def test_routes_main_to_acceptance_of_configured_release_line(self) -> None:
        """Verwendet für main die versionierte führende Releaselinie und Abnahme.

        Der Branchname enthält bei main keine Releaselinie. Die Konfiguration
        weist main deshalb R270 zu, deren ETAPS-Linie en02 ist.
        """

        git(self.repository, "branch", "-m", "main")
        git(self.repository, "update-ref", "refs/remotes/origin/main", "HEAD")
        with (
            patch("lbs_delivery.sync.publish_full_server_sync"),
            patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter,
        ):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="main",
                staging_root=self.root / "main-staging",
                server_sync_root=self.root / "main-serverSync",
            )
        adapter.assert_called_once_with(
            "https://en02a.ltoma.intern/vMtextAdapter/sync",
            timeout=30.0,
        )


if __name__ == "__main__":
    unittest.main()
