"""Prüft Projektpakete, CIFS-Übergabe und Adapterauftrag des Sync-Wegs."""

from __future__ import annotations

import json
import os
import tarfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mtext

from lbs_delivery import sync as sync_command

from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.sync import sync_resources

from tests.support import TempDirTestCase, git, load_test_configuration, setup_sync_repository


# Ein fester GitHub-Kontext macht die Weitergabe des Ereignisvergleichs prüfbar.
GITHUB_CONTEXT = {
    "commit": "2" * 40,
    "source_branch": "main",
    "event_name": "push",
    "previous_commit": "1" * 40,
}

# Der Vorgängerstand einer Konfigurationsänderung führt noch die alte Releaselinie.
PREVIOUS_CONFIG = json.dumps({"mandant": {"releaselinie": "R261"}}).encode()


class SyncTests(TempDirTestCase):
    """Prüft die fachlichen Sync-Umfänge und ihre technische Übergabe."""

    def setUp(self) -> None:
        """Bereitet Repository, Konfiguration und CIFS-Testwurzel vor."""

        super().setUp()
        self.repository = setup_sync_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.branch = "feature/R261/test-sync"
        self.handoff_root = self.root / "cifs"
        self.handoff_root.mkdir()

    def sync(self, commit: str, previous_commit: str | None, **kwargs: object) -> dict[str, object]:
        """Startet einen Sync-Lauf mit den gemeinsamen Testangaben."""

        return sync_resources(
            self.configuration,
            repository_root=self.repository,
            commit=commit,
            previous_commit=previous_commit,
            source_branch=self.branch,
            releaselinie="R261",
            zielstufe="Entwicklung",
            handoff_root=self.handoff_root,
            **kwargs,
        )

    def track_branch(self) -> None:
        """Aktualisiert den vom Produktivcode geprüften Remote-Branch."""

        git(self.repository, "update-ref", f"refs/remotes/origin/{self.branch}", "HEAD")

    def test_run_command(self) -> None:
        """Prüft Vollabgleich, Ereignisvergleich und Fehlerkontext der Ablaufsteuerung."""

        configuration = SimpleNamespace(releaselinie="R270", warnungen=())
        arguments = SimpleNamespace(commit=GITHUB_CONTEXT["commit"])
        environment = {
            "GITHUB_WORKSPACE": str(self.root),
            "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "GITHUB_REF_NAME": GITHUB_CONTEXT["source_branch"],
            "GITHUB_EVENT_NAME": GITHUB_CONTEXT["event_name"],
            "MTEXT_PREVIOUS_COMMIT": GITHUB_CONTEXT["previous_commit"],
        }

        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(sync_command.config, "load_configuration", return_value=configuration),
            patch.object(sync_command.git, "read_file", return_value=PREVIOUS_CONFIG),
            patch.object(
                sync_command,
                "sync_resources",
                side_effect=({"status": Status.ADAPTER_ACCEPTED.value}, {"status": Status.ADAPTER_ACCEPTED.value}),
            ) as synchronize,
        ):
            result = sync_command.run_command(arguments)
        self.assertEqual([entry["zielstufe"] for entry in result["synchronisationen"]], ["Entwicklung", "Funktionstest"])
        self.assertTrue(all(call.kwargs["previous_commit"] is None for call in synchronize.call_args_list))

        with (
            patch.dict(os.environ, environment | {"GITHUB_REF_NAME": "feature/R271/test"}, clear=True),
            patch.object(sync_command.config, "load_configuration", return_value=configuration),
            patch.object(sync_command, "sync_resources", return_value={"status": Status.ADAPTER_ACCEPTED.value}) as synchronize,
        ):
            sync_command.run_command(arguments)
        self.assertEqual(synchronize.call_args.kwargs["previous_commit"], "1" * 40)

        with (
            patch.dict(
                os.environ,
                environment | {"GITHUB_REF_NAME": "feature/R271/test", "MTEXT_PREVIOUS_COMMIT": sync_command.EMPTY_PUSH_COMMIT},
                clear=True,
            ),
            patch.object(sync_command.config, "load_configuration", return_value=configuration),
            patch.object(sync_command, "sync_resources", return_value={"status": Status.ADAPTER_ACCEPTED.value}) as synchronize,
        ):
            sync_command.run_command(arguments)
        self.assertIsNone(synchronize.call_args.kwargs["previous_commit"])

        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(sync_command.config, "load_configuration", return_value=configuration),
            patch.object(sync_command.git, "read_file", return_value=PREVIOUS_CONFIG),
            patch.object(
                sync_command,
                "sync_resources",
                side_effect=(
                    {"status": Status.ADAPTER_ACCEPTED.value},
                    DeliveryError(Status.ADAPTER_FAILED, "Adapter nicht erreichbar"),
                ),
            ),
            self.assertRaisesRegex(DeliveryError, "Bereits erfolgreich: Entwicklung"),
        ):
            sync_command.run_command(arguments)

    def test_delta_package_uses_only_event_changes(self) -> None:
        """Prüft D-Archiv, Löschliste, JSON und Adapterauftrag eines Pushs."""

        project = self.repository / "LOMS_Basis"
        (project / "unchanged.txt").write_text("same", encoding="utf-8")
        (project / "deleted.txt").write_text("delete", encoding="utf-8")
        (project / "rename-old.txt").write_text("rename", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "base")
        previous_commit = git(self.repository, "rev-parse", "HEAD")

        (project / "value.txt").write_text("changed", encoding="utf-8")
        (project / "new.txt").write_text("new", encoding="utf-8")
        (project / "deleted.txt").unlink()
        git(self.repository, "mv", "LOMS_Basis/rename-old.txt", "LOMS_Basis/rename-new.txt")
        git(self.repository, "add", "-A")
        git(self.repository, "commit", "-m", "delta")
        self.track_branch()
        commit = git(self.repository, "rev-parse", "HEAD")

        with (
            patch("lbs_delivery.sync.uuid.uuid4", return_value=SimpleNamespace(hex="auftrag")),
            patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter,
        ):
            result = self.sync(commit, previous_commit)

        request_path = Path(result["pfad"])
        self.assertEqual(request_path, self.handoff_root / "en01" / f"FI-{commit[:12]}-auftrag")
        self.assertEqual(sorted(path.name for path in request_path.iterdir()), [
            "FIBASISD.tgz",
            "_INFO_FI-LOMS_Basis.json",
        ])

        information = json.loads((request_path / "_INFO_FI-LOMS_Basis.json").read_text(encoding="utf-8"))
        self.assertEqual(information["stand"]["von"]["commit"], previous_commit)
        self.assertEqual(information["stand"]["bis"]["commit"], commit)
        self.assertIn(["D", "deleted.txt"], information["elemente"])
        self.assertNotIn(["M", "unchanged.txt"], information["elemente"])

        with tarfile.open(request_path / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion)
            deleted = deletion.read().decode()
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)

        payload = adapter.call_args.args[1]
        self.assertEqual(payload["pfad"], str(request_path))
        self.assertEqual(payload["projekte"], ["LOMS_Basis"])
        self.assertEqual(payload["von"], previous_commit)
        self.assertEqual(payload["bis"], commit)

        with (
            patch("lbs_delivery.sync.uuid.uuid4", return_value=SimpleNamespace(hex="wiederholung")),
            patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as repeated_adapter,
        ):
            self.sync(commit, previous_commit)
        repeated_payload = repeated_adapter.call_args.args[1]
        self.assertEqual(repeated_payload["auftrag"], payload["auftrag"])
        self.assertNotEqual(repeated_payload["pfad"], payload["pfad"])

    def test_full_package_and_empty_sync(self) -> None:
        """Prüft FULL beim fehlenden Vorgänger und den Lauf ohne Projektänderung."""

        commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter", return_value=(202, "angenommen")) as adapter:
            result = self.sync(commit, None)
        request_path = Path(result["pfad"])
        self.assertTrue((request_path / "FIBASISF.tgz").is_file())
        self.assertTrue((request_path / "FIBASISD.tgz").is_file())
        information = json.loads((request_path / "_INFO_FI-LOMS_Basis.json").read_text(encoding="utf-8"))
        self.assertNotIn("von", information["stand"])
        self.assertEqual(set(information["sha256"]), {"F", "D"})
        self.assertNotIn("von", adapter.call_args.args[1])
        adapter.assert_called_once()

        (self.repository / ".github/note.txt").write_text("keine Projektänderung", encoding="utf-8")
        git(self.repository, "add", ".github")
        git(self.repository, "commit", "-m", "Metadaten")
        self.track_branch()
        metadata_commit = git(self.repository, "rev-parse", "HEAD")
        with patch("lbs_delivery.sync.call_adapter") as adapter:
            result = self.sync(metadata_commit, commit)
        self.assertEqual(result["projekte"], [])
        adapter.assert_not_called()

    def test_rejects_missing_cifs_and_invalid_target(self) -> None:
        """Prüft die echten Systemgrenzen vor dem Paketbau."""

        commit = git(self.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(DeliveryError, "CIFS-Übergabepfad"):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                previous_commit=None,
                source_branch=self.branch,
                releaselinie="R261",
                zielstufe="Entwicklung",
                handoff_root=self.root / "fehlt",
            )
        with self.assertRaisesRegex(DeliveryError, "Zielstufe"):
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=commit,
                previous_commit=None,
                source_branch=self.branch,
                releaselinie="R261",
                zielstufe="Unbekannt",
                handoff_root=self.handoff_root,
            )

    def test_run_reads_cifs_environment(self) -> None:
        """Prüft die Übergabe des GitHub- und Runner-Kontexts an den Ablauf."""

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
            patch("sys.argv", ["mtext.py", "sync-resources", "--commit", "2" * 40]),
            patch.object(mtext.config, "load_configuration", return_value=SimpleNamespace(warnungen=())),
            patch.object(mtext.sync, "plan_sync", return_value=("R261", (), "1" * 40)) as plan,
        ):
            self.assertEqual(mtext.run(), response)
        self.assertEqual(plan.call_args.kwargs["previous_commit"], "1" * 40)


if __name__ == "__main__":
    unittest.main()
