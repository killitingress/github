"""Prüft die direkte Aktualisierung der M/Text-Ressourcen unter serverSync.

Externe Adapter- und Zielpfade werden bei Bedarf abgegrenzt. Echte
Verzeichnisbäume prüfen dabei das Synchronisationsverhalten.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sync_resources as sync_command

from lbs_delivery.git import resolve_sync_branch
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.sync import (
    _apply_server_sync_changes,
    sync_resources,
)

from tests.support import git, load_test_configuration, setup_sync_repository


def _github_configuration(releaselinie: str = "R270") -> SimpleNamespace:
    """Liefert eine minimale Konfiguration für Orchestration-Tests."""

    return SimpleNamespace(releaselinie=releaselinie, warnungen=())


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

    def test_resolve_sync_branch(self) -> None:
        """Ordnet Feature- und Zielbranches der Releaselinie und Zielstufe zu."""

        self.assertEqual(
            resolve_sync_branch("feature/R271/brief/anschreiben", "R270"),
            ("R271", "Entwicklung"),
        )
        with self.assertRaises(DeliveryError):
            resolve_sync_branch("feature/R271/", "R270")

    def test_release_change_reads_previous_configuration(self) -> None:
        """Liest oder lehnt die führende Releaselinie aus dem vorherigen Commit ab."""

        configuration_path = self.repository / ".github/config.json"
        configuration_path.parent.mkdir(exist_ok=True)

        with self.subTest(gueltig=True):
            configuration_path.write_text(
                json.dumps({"mandant": {"releaselinie": "R261"}}),
                encoding="utf-8",
            )
            git(self.repository, "add", str(configuration_path.relative_to(self.repository)))
            git(self.repository, "commit", "-m", "old release line")
            previous_commit = git(self.repository, "rev-parse", "HEAD")
            with patch.object(
                sync_command,
                "sync_resources",
                return_value={"status": Status.ADAPTER_ACCEPTED.value},
            ) as synchronize:
                sync_command.sync_from_github_context(
                    _github_configuration(),
                    repository_root=self.repository,
                    commit="2" * 40,
                    source_branch="main",
                    event_name="push",
                    previous_commit=previous_commit,
                )
            self.assertEqual(synchronize.call_count, 2)

        with self.subTest(gueltig=False):
            configuration_path.write_text(json.dumps({"mandant": {}}), encoding="utf-8")
            git(self.repository, "add", str(configuration_path.relative_to(self.repository)))
            git(self.repository, "commit", "-m", "invalid old configuration")
            with self.assertRaisesRegex(DeliveryError, "Bisherige Mandantenkonfiguration"):
                sync_command.sync_from_github_context(
                    _github_configuration(),
                    repository_root=self.repository,
                    commit="2" * 40,
                    source_branch="main",
                    event_name="push",
                    previous_commit=git(self.repository, "rev-parse", "HEAD"),
                )

    def test_sync_from_github_context_plans_targets_and_reports_partial_success(self) -> None:
        """Plant Zielstufen aus dem GitHub-Kontext, meldet Teilerfolge und reicht CLI-Kontext durch."""

        configuration = _github_configuration()
        context = {
            "configuration": configuration,
            "repository_root": self.repository,
            "commit": "2" * 40,
            "source_branch": "main",
            "event_name": "push",
            "previous_commit": "1" * 40,
        }

        with self.subTest(releasewechsel=True):
            with (
                patch.object(
                    sync_command,
                    "read_file",
                    return_value=json.dumps({"mandant": {"releaselinie": "R261"}}).encode(),
                ),
                patch.object(
                    sync_command,
                    "sync_resources",
                    side_effect=(
                        {"status": Status.ADAPTER_ACCEPTED.value},
                        {"status": Status.ADAPTER_ACCEPTED.value},
                    ),
                ) as synchronize,
            ):
                result = sync_command.sync_from_github_context(**context)
            self.assertEqual(
                [entry["zielstufe"] for entry in result["synchronisationen"]],
                ["Entwicklung", "Abnahme"],
            )
            self.assertEqual(
                [call.kwargs["zielstufe"] for call in synchronize.call_args_list],
                ["Entwicklung", "Abnahme"],
            )
            self.assertTrue(all(call.kwargs["vollabgleich"] for call in synchronize.call_args_list))

        with self.subTest(manuell=True):
            with patch(
                "sync_resources.sync_resources",
                return_value={"status": Status.ADAPTER_ACCEPTED.value},
            ) as synchronize:
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

        with self.subTest(teilerfolg=True):
            with (
                patch.object(
                    sync_command,
                    "read_file",
                    return_value=json.dumps({"mandant": {"releaselinie": "R261"}}).encode(),
                ),
                patch.object(
                    sync_command,
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

        with self.subTest(cli=True):
            environment = {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                "GITHUB_REF_NAME": "main",
                "GITHUB_EVENT_NAME": "push",
                "MTEXT_PREVIOUS_COMMIT": "1" * 40,
                "RUNNER_TEMP": str(self.root),
            }
            response = {"status": Status.ADAPTER_ACCEPTED.value, "synchronisationen": []}
            with (
                patch.dict(os.environ, environment, clear=True),
                patch("sys.argv", ["sync_resources.py", "--commit", "2" * 40]),
                patch.object(sync_command, "load_configuration", return_value=self.configuration),
                patch.object(sync_command, "sync_from_github_context", return_value=response) as synchronize,
            ):
                self.assertEqual(sync_command.run(), response)
            self.assertEqual(synchronize.call_args.kwargs["previous_commit"], "1" * 40)

    def test_sync_targets_complete_project_and_rejects_invalid_branch(self) -> None:
        """Prüft Vollabgleich und Zuordnung von Branch zu M/Text-Ziel."""

        target = self.root / "serverSync"
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter:
            result = sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="feature/R261/test-sync",
                releaselinie="R261",
                zielstufe="Entwicklung",
                server_sync_root=target,
            )
        self.assertEqual(result["status"], Status.ADAPTER_ACCEPTED.value)
        adapter.assert_called_once_with(
            "https://en01e.ltoma.intern/vMtextAdapter/sync",
            timeout=30.0,
        )
        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "new")

        with self.assertRaises(DeliveryError):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="unbekannt",
                releaselinie="R261",
                zielstufe="Entwicklung",
                server_sync_root=target,
            )

    def test_incremental_server_sync(self) -> None:
        """Überträgt nur geänderte Ressourcen und verarbeitet Commits ohne Ressourcenänderung."""

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
                releaselinie="R261",
                zielstufe="Entwicklung",
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
                releaselinie="R261",
                zielstufe="Entwicklung",
                server_sync_root=target,
            )

        self.assertEqual((target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"), "changed")
        self.assertEqual((target / "LOMS_Basis/new.txt").read_text(encoding="utf-8"), "new")
        self.assertFalse((target / "LOMS_Basis/deleted.txt").exists())
        self.assertFalse((target / "LOMS_Basis/rename-old.txt").exists())
        self.assertEqual((target / "LOMS_Basis/rename-new.txt").read_text(encoding="utf-8"), "rename")
        self.assertEqual((target / "LOMS_Basis/unchanged.txt").stat().st_mtime_ns, unchanged_mtime)

        note = self.repository / ".github/note.txt"
        note.parent.mkdir(exist_ok=True)
        note.write_text("keine Ressourcenänderung", encoding="utf-8")
        git(self.repository, "add", ".github")
        git(self.repository, "commit", "-m", "change workflow metadata")
        git(self.repository, "update-ref", "refs/remotes/origin/feature/R261/test-sync", "HEAD")
        third_commit = git(self.repository, "rev-parse", "HEAD")
        value_mtime = (target / "LOMS_Basis/value.txt").stat().st_mtime_ns

        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter:
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=third_commit,
                source_branch="feature/R261/test-sync",
                releaselinie="R261",
                zielstufe="Entwicklung",
                server_sync_root=target,
            )

        self.assertEqual((target / "LOMS_Basis/value.txt").stat().st_mtime_ns, value_mtime)
        adapter.assert_called_once()
        marker = json.loads((target / ".mtext-sync/FI.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["commit"], third_commit)

    def test_incremental_publish_can_be_repeated_after_failure(self) -> None:
        """Wendet dieselben Änderungen nach einem teilweisen Fehler erneut an."""

        source = self.root / "retry-source/LOMS_Basis"
        source.mkdir(parents=True)
        (source / "changed.txt").write_text("new", encoding="utf-8")
        target = self.root / "retry-serverSync"
        project = target / "LOMS_Basis"
        project.mkdir(parents=True)
        (project / "deleted.txt").write_text("old deleted", encoding="utf-8")
        (project / "changed.txt").write_text("old changed", encoding="utf-8")

        with (
            patch("lbs_delivery.sync.shutil.copy2", side_effect=OSError("copy failed")),
            self.assertRaisesRegex(DeliveryError, "serverSync-Veröffentlichung fehlgeschlagen"),
        ):
            _apply_server_sync_changes(
                source.parent,
                target,
                [("D", "LOMS_Basis/deleted.txt"), ("M", "LOMS_Basis/changed.txt")],
            )

        self.assertFalse((project / "deleted.txt").exists())
        self.assertEqual((project / "changed.txt").read_text(encoding="utf-8"), "old changed")

        _apply_server_sync_changes(
            source.parent,
            target,
            [("D", "LOMS_Basis/deleted.txt"), ("M", "LOMS_Basis/changed.txt")],
        )
        self.assertFalse((project / "deleted.txt").exists())
        self.assertEqual((project / "changed.txt").read_text(encoding="utf-8"), "new")

        (source / "changed.txt").unlink()
        with self.assertRaisesRegex(DeliveryError, "geänderte Ressource fehlt"):
            _apply_server_sync_changes(
                source.parent,
                target,
                [("M", "LOMS_Basis/changed.txt")],
            )

    def test_full_sync_can_be_repeated_after_copy_failure(self) -> None:
        """Stellt einen beim Kopieren unterbrochenen Vollabgleich beim Wiederanlauf fertig."""

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
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                source_branch="feature/R261/test-sync",
                releaselinie="R261",
                zielstufe="Entwicklung",
                vollabgleich=True,
                server_sync_root=target,
            )
        adapter.assert_not_called()
        self.assertFalse(project.exists())
        self.assertFalse((target / ".mtext-sync/FI.json").exists())

        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                source_branch="feature/R261/test-sync",
                releaselinie="R261",
                zielstufe="Entwicklung",
                vollabgleich=True,
                server_sync_root=target,
            )
        self.assertEqual((project / "value.txt").read_text(encoding="utf-8"), "new")
        marker = json.loads((target / ".mtext-sync/FI.json").read_text(encoding="utf-8"))
        self.assertEqual(marker["commit"], commit)

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
                        releaselinie="R261",
                        zielstufe="Entwicklung",
                        server_sync_root=target,
                    )

    def test_manual_sync_uses_branch_target_and_full_project(self) -> None:
        """Gleicht einen Commit vollständig mit dem Ziel seines Branches ab."""

        commit = git(self.repository, "rev-parse", "HEAD")
        cases = (
            ("feature/R261/test-sync", "R261", "Entwicklung", "en01e"),
            ("main", "R270", "Abnahme", "en02a"),
        )
        for source_branch, releaselinie, zielstufe, host in cases:
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
                marker.write_text(
                    json.dumps({"repository": self.configuration.repository, "commit": commit}),
                    encoding="utf-8",
                )
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
                adapter.assert_called_once_with(
                    f"https://{host}.ltoma.intern/vMtextAdapter/sync",
                    timeout=30.0,
                )

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
