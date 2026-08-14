"""Prüft die Aktualisierung der M/Text-Ressourcen unter serverSync."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sync_resources as sync_command

from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.sync import _apply_server_sync_changes, sync_resources

from tests.support import TempDirTestCase, git, load_test_configuration, setup_sync_repository

GITHUB_CONTEXT = {
    "commit": "2" * 40,
    "source_branch": "main",
    "event_name": "push",
    "previous_commit": "1" * 40,
}
PREVIOUS_CONFIG = json.dumps({"mandant": {"releaselinie": "R261"}}).encode()


class SyncTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = setup_sync_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.branch = "feature/R261/test-sync"

    def sync(self, commit: str, target: Path, **kwargs) -> None:
        sync_resources(
            self.configuration,
            repository_root=self.repository,
            commit=commit,
            source_branch=self.branch,
            releaselinie="R261",
            zielstufe="Entwicklung",
            server_sync_root=target,
            **kwargs,
        )

    def track_branch(self) -> None:
        git(self.repository, "update-ref", f"refs/remotes/origin/{self.branch}", "HEAD")

    def test_sync_from_github_context(self) -> None:
        configuration = SimpleNamespace(releaselinie="R270", warnungen=())
        context = {"configuration": configuration, "repository_root": self.repository, **GITHUB_CONTEXT}

        with (
            patch.object(sync_command.git, "read_file", return_value=PREVIOUS_CONFIG),
            patch.object(
                sync_command.sync,
                "sync_resources",
                side_effect=({"status": Status.ADAPTER_ACCEPTED.value}, {"status": Status.ADAPTER_ACCEPTED.value}),
            ) as synchronize,
        ):
            result = sync_command.sync_from_github_context(**context)
        self.assertEqual([entry["zielstufe"] for entry in result["synchronisationen"]], ["Entwicklung", "Funktionstest"])
        self.assertEqual([call.kwargs["zielstufe"] for call in synchronize.call_args_list], ["Entwicklung", "Funktionstest"])
        self.assertTrue(all(call.kwargs["vollabgleich"] for call in synchronize.call_args_list))

        with (
            patch.object(sync_command.git, "read_file", return_value=json.dumps({"mandant": {}}).encode()),
            self.assertRaises(KeyError),
        ):
            sync_command.sync_from_github_context(**context)

        with patch.object(sync_command.sync, "sync_resources", return_value={"status": Status.ADAPTER_ACCEPTED.value}) as synchronize:
            result = sync_command.sync_from_github_context(
                configuration,
                repository_root=self.repository,
                commit="2" * 40,
                source_branch="feature/R271/wiederherstellung",
                event_name="workflow_dispatch",
                previous_commit="",
            )
        self.assertEqual(result["synchronisationen"][0]["zielstufe"], "Entwicklung")
        self.assertTrue(synchronize.call_args.kwargs["vollabgleich"])

        with (
            patch.object(sync_command.git, "read_file", return_value=PREVIOUS_CONFIG),
            patch.object(
                sync_command.sync,
                "sync_resources",
                side_effect=(
                    {"status": Status.ADAPTER_ACCEPTED.value},
                    DeliveryError(Status.ADAPTER_FAILED, "Adapter nicht erreichbar"),
                ),
            ) as synchronize,
            self.assertRaisesRegex(DeliveryError, "Bereits erfolgreich: Entwicklung"),
        ):
            sync_command.sync_from_github_context(**context)
        self.assertEqual(synchronize.call_count, 2)

        response = {"status": Status.ADAPTER_ACCEPTED.value, "synchronisationen": []}
        with (
            patch.dict(
                os.environ,
                {
                    "GITHUB_WORKSPACE": str(self.root),
                    "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                    "GITHUB_REF_NAME": "main",
                    "GITHUB_EVENT_NAME": "push",
                    "MTEXT_PREVIOUS_COMMIT": "1" * 40,
                },
                clear=True,
            ),
            patch("sys.argv", ["sync_resources.py", "--commit", "2" * 40]),
            patch.object(sync_command.config, "load_configuration", return_value=self.configuration),
            patch.object(sync_command, "sync_from_github_context", return_value=response) as synchronize,
        ):
            self.assertEqual(sync_command.run(), response)
        self.assertEqual(synchronize.call_args.kwargs["previous_commit"], "1" * 40)

    def test_incremental_server_sync(self) -> None:
        project = self.repository / "LOMS_Basis"
        (project / "unchanged.txt").write_text("same", encoding="utf-8")
        (project / "deleted.txt").write_text("delete", encoding="utf-8")
        (project / "rename-old.txt").write_text("rename", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "add unchanged resource")
        self.track_branch()

        target = self.root / "persistent-serverSync"
        first_commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            self.sync(first_commit, target)
        unchanged_mtime = (target / "LOMS_Basis/unchanged.txt").stat().st_mtime_ns

        (project / "value.txt").write_text("changed", encoding="utf-8")
        (project / "new.txt").write_text("new", encoding="utf-8")
        (project / "deleted.txt").unlink()
        git(self.repository, "mv", "LOMS_Basis/rename-old.txt", "LOMS_Basis/rename-new.txt")
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-m", "change resources")
        self.track_branch()
        second_commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            self.sync(second_commit, target)

        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "changed")
        self.assertEqual((target / "LOMS_Basis/new.txt").read_text(encoding="utf-8"), "new")
        self.assertFalse((target / "LOMS_Basis/deleted.txt").exists())
        self.assertFalse((target / "LOMS_Basis/rename-old.txt").exists())
        self.assertEqual((target / "LOMS_Basis/rename-new.txt").read_text(encoding="utf-8"), "rename")
        self.assertEqual((target / "LOMS_Basis/unchanged.txt").stat().st_mtime_ns, unchanged_mtime)

        (self.repository / ".github/note.txt").parent.mkdir(exist_ok=True)
        (self.repository / ".github/note.txt").write_text("keine Ressourcenänderung", encoding="utf-8")
        git(self.repository, "add", ".github")
        git(self.repository, "commit", "-m", "change workflow metadata")
        self.track_branch()
        third_commit = git(self.repository, "rev-parse", "HEAD")
        value_mtime = (target / "LOMS_Basis/value.txt").stat().st_mtime_ns
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter:
            self.sync(third_commit, target)
        self.assertEqual((target / "LOMS_Basis/value.txt").stat().st_mtime_ns, value_mtime)
        adapter.assert_called_once()
        marker = json.loads((target / ".mtext-sync/FI.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["commit"], third_commit)

    def test_server_sync_recovers_from_failures_and_rejects_invalid_marker(self) -> None:
        source = self.root / "retry-source/LOMS_Basis"
        source.mkdir(parents=True)
        (source / "changed.txt").write_text("new", encoding="utf-8")
        target = self.root / "retry-serverSync"
        project = target / "LOMS_Basis"
        project.mkdir(parents=True)
        (project / "deleted.txt").write_text("old deleted", encoding="utf-8")
        (project / "changed.txt").write_text("old changed", encoding="utf-8")
        operations = [("D", "LOMS_Basis/deleted.txt"), ("M", "LOMS_Basis/changed.txt")]

        with (
            patch("lbs_delivery.sync.shutil.copy2", side_effect=OSError("copy failed")),
            self.assertRaisesRegex(DeliveryError, "serverSync-Veröffentlichung fehlgeschlagen"),
        ):
            _apply_server_sync_changes(source.parent, target, operations)
        self.assertFalse((project / "deleted.txt").exists())
        self.assertEqual((project / "changed.txt").read_text(encoding="utf-8"), "old changed")

        _apply_server_sync_changes(source.parent, target, operations)
        self.assertFalse((project / "deleted.txt").exists())
        self.assertEqual((project / "changed.txt").read_text(encoding="utf-8"), "new")

        commit = git(self.repository, "rev-parse", "HEAD")
        target = self.root / "full-retry-serverSync"
        project = target / "LOMS_Basis"
        project.mkdir(parents=True)
        (project / "stale.txt").write_text("stale", encoding="utf-8")
        with (
            patch("lbs_delivery.sync.shutil.copytree", side_effect=OSError("copy failed")),
            patch("lbs_delivery.sync.call_adapter") as adapter,
            self.assertRaisesRegex(DeliveryError, "serverSync-Veröffentlichung fehlgeschlagen"),
        ):
            self.sync(commit, target, vollabgleich=True)
        adapter.assert_not_called()
        self.assertFalse(project.exists())
        self.assertFalse((target / ".mtext-sync/FI.json").exists())

        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            self.sync(commit, target, vollabgleich=True)
        self.assertEqual((project / "value.txt").read_text(encoding="utf-8"), "new")
        marker = json.loads((target / ".mtext-sync/FI.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["commit"], commit)

        for index, marker_value in enumerate(
            ("kein JSON", json.dumps({"repository": "anderes/repository", "commit": commit}))
        ):
            with self.subTest(marker=index):
                invalid_target = self.root / f"invalid-marker-{index}"
                marker_path = invalid_target / ".mtext-sync/FI.json"
                marker_path.parent.mkdir(parents=True)
                marker_path.write_text(marker_value, encoding="utf-8")
                with self.assertRaisesRegex(DeliveryError, "Synchronisationsstand ist ungültig"):
                    self.sync(commit, invalid_target)

    def test_manual_sync_uses_branch_target_and_full_project(self) -> None:
        commit = git(self.repository, "rev-parse", "HEAD")
        for source_branch, releaselinie, zielstufe, host in (
            ("feature/R261/test-sync", "R261", "Entwicklung", "en01"),
            ("main", "R270", "Funktionstest", "fu02"),
        ):
            with self.subTest(source_branch=source_branch):
                if source_branch == "main":
                    git(self.repository, "branch", "main", "HEAD")
                    git(self.repository, "update-ref", "refs/remotes/origin/main", "HEAD")
                target = self.root / f"manual-{host}-serverSync"
                project = target / "LOMS_Basis"
                project.mkdir(parents=True)
                (project / "stale.txt").write_text("stale", encoding="utf-8")
                marker = target / ".mtext-sync/FI.json"
                marker.parent.mkdir()
                marker.write_text(json.dumps({"repository": self.configuration.repository, "commit": commit}), encoding="utf-8")
                with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter:
                    sync_resources(
                        self.configuration,
                        repository_root=self.repository,
                        commit=commit,
                        source_branch=source_branch,
                        releaselinie=releaselinie,
                        zielstufe=zielstufe,
                        vollabgleich=True,
                        server_sync_root=target,
                    )
                self.assertFalse((project / "stale.txt").exists())
                adapter.assert_called_once_with(f"https://{host}.ltoma.intern/vMtextAdapter/sync")

        git(self.repository, "update-ref", "refs/remotes/origin/main", "HEAD")
        with self.assertRaisesRegex(DeliveryError, "Zielstufe"):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                source_branch="main",
                releaselinie="R270",
                zielstufe="Unbekannt",
                vollabgleich=True,
                server_sync_root=self.root / "manual-invalid-serverSync",
            )


if __name__ == "__main__":
    unittest.main()
