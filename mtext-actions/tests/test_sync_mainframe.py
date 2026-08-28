"""Prüft Sync-Vergleichsstände, Paketübergabe und den HTTPS-Adaptervertrag."""

from __future__ import annotations

import json
import os
import unittest
import urllib.error
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from lbs_delivery import adapter, github, sync
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.project_package import ProjectPackage
from tests.support import TempDirTestCase, git, load_test_configuration, setup_release_repository


class SyncTests(TempDirTestCase):
    """Prüft die Sync-Regeln mit gemeinsamer Git-Historie und simuliertem Adapter."""

    def setUp(self) -> None:
        """Stellt Mandantenstand und Workflow-Umgebung für die Sync-Aufrufe bereit."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        configuration = load_test_configuration(self.repository)
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(self.root),
            "GITHUB_REPOSITORY": configuration.repository,
            "GITHUB_REF_NAME": "release/261",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_RUN_ID": "test",
            "GITHUB_API_URL": "https://github.test/api/v3",
            "GITHUB_TOKEN": "test-token",
            "MTEXT_PREVIOUS_COMMIT": "before",
        }))
        self.package = ProjectPackage(self.root / "info.json", self.root / "namedF.tgz", self.root / "full.tgz")
        for path in (self.package.information, self.package.d_archiv, self.package.f_archiv):
            path.write_bytes(b"Paketinhalt")

    def test_run_command(self) -> None:
        """Prüft Erstlauf, DELTA-Basis, Linienwechsel, manuelles FULL und überholte Läufe."""

        with (
            patch.object(github, "request") as history,
            patch.object(sync.git, "resolve", return_value="current"),
            patch.object(sync.git, "require_ancestor") as ancestor,
            patch.object(sync.git, "changes", return_value=[]),
            patch.object(sync.git, "execute") as read_git,
            patch.object(sync, "_sync_zielstufe", return_value={}) as transfer,
        ):
            # Der letzte Erfolg bestimmt das DELTA. Ein manueller Lauf bestätigt
            # keinen ausstehenden Linienwechsel für beide Zielstufen.
            for branch, event, commits, old_line, base, targets in (
                ("feature/261/test", "push", ["previous"], "270", "previous", ["Entwicklung"]),
                ("feature/261/test", "push", [None], "270", "base", ["Entwicklung"]),
                ("release/261", "push", [None], "270", None, ["Funktionstest"]),
                ("main", "push", ["previous", "previous"], "270", "previous", ["Funktionstest"]),
                ("main", "push", ["current", "previous"], "261", None, ["Entwicklung", "Funktionstest"]),
                ("main", "push", ["current", None], "261", None, ["Entwicklung", "Funktionstest"]),
                ("main", "push", ["current", "current"], "270", "current", ["Funktionstest"]),
                ("main", "workflow_dispatch", [], "261", None, ["Funktionstest"]),
                ("feature/261/test", "workflow_dispatch", [], "270", None, ["Entwicklung"]),
            ):
                history.reset_mock()
                history.side_effect = [
                    {"workflow_runs": [{"head_sha": commit}] if commit else []} for commit in commits
                ]
                read_git.reset_mock()
                read_git.return_value = (
                    json.dumps({"mandant": {"releaselinie": old_line}}).encode() if branch == "main" else b"base"
                )
                transfer.reset_mock()
                ancestor.reset_mock()
                with self.subTest(branch=branch, event=event, commits=commits), patch.dict(os.environ, {
                    "GITHUB_REF_NAME": branch, "GITHUB_EVENT_NAME": event,
                }):
                    result = sync.run(SimpleNamespace())
                    self.assertEqual([entry["zielstufe"] for entry in result["synchronisationen"]], targets)
                    for invocation in transfer.call_args_list:
                        self.assertEqual(invocation.kwargs["stand"].von, (branch, base) if base else None)
                    self.assertEqual(history.call_count, len(commits))
                    branch_check = call(self.repository, "current", f"refs/remotes/origin/{branch}")
                    self.assertEqual(ancestor.call_args_list.count(branch_check), 1)

                    if len(commits) == 2:
                        self.assertIn("event=push", history.call_args.kwargs["url"])
                        reference = f"{commits[1] or 'before'}:{sync.config.MANDANT_CONFIG_PATH}"
                        read_git.assert_called_once_with(self.repository, "show", reference)

                    if base == "base":
                        read_git.assert_called_with(
                            self.repository, "merge-base", "current", "refs/remotes/origin/release/261",
                        )

            history.side_effect = [{"workflow_runs": [{"head_sha": "previous"}]}]
            ancestor.side_effect = DeliveryError(Status.SOURCE_FAILED, "kein Vorfahr")
            transfer.reset_mock()
            with self.assertRaisesRegex(DeliveryError, "Der Lauf ist überholt"):
                sync.run(SimpleNamespace())
            transfer.assert_not_called()

    def test_sync_packages(self) -> None:
        """Prüft kumulative Sync-Änderungen, FULL und das Auslassen reiner Konfigurationsänderungen."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        commit = git(self.repository, "rev-parse", "HEAD")
        documents = []

        def capture_packages(*_args, packages, **_kwargs) -> str:
            """Liest die erzeugten Paketinformationen während ihrer Übergabe."""

            for _project, package in packages:
                documents.append(json.loads(package.information.read_text()))
            return "auftrag"

        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "synchronize", side_effect=capture_packages) as transfer,
        ):
            for event in ("push", "workflow_dispatch"):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event}):
                    sync.run(SimpleNamespace())
            self.assertEqual(documents[0]["stand"]["von"]["commit"], baseline)
            self.assertEqual(documents[0]["stand"]["bis"]["commit"], commit)
            self.assertIn(["M", "baseline.txt"], documents[0]["elemente"])
            self.assertNotIn("von", documents[1]["stand"])
            self.assertEqual([set(document["sha256"]) for document in documents], [{"D"}, {"D", "F"}])

            git(self.repository, "add", ".github")
            git(self.repository, "commit", "-m", "Konfiguration")
            git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
            transfer.reset_mock()
            with patch.object(github, "last_sync_commit", return_value=commit):
                result = sync.run(SimpleNamespace())
            self.assertEqual(result["synchronisationen"][0]["projekte"], [])
            transfer.assert_not_called()

    def test_adapter_protocol(self) -> None:
        """Prüft HTTP-Ablauf, Multipart-Felder, Wiederaufnahme und Fehler bis zum Löschen."""

        uploading = {"auftrag_id": "auftrag", "status": "uploading"}
        queued = uploading | {"status": "queued"}
        succeeded = uploading | {"status": "succeeded"}
        failed = uploading | {"status": "failed", "meldung": "M/Text-Fehler"}
        network_error = urllib.error.URLError("Verbindung abgebrochen")
        response = MagicMock(status=200)
        response.__enter__.return_value = response

        def receive(request, **_kwargs) -> MagicMock:
            """Liest den echten Multipart-Datenstrom und prüft dessen Feldzuordnung."""

            if request.get_method() == "PUT":
                self.assertNotIsInstance(request.data, bytes)
                body = b"".join(request.data)
                self.assertEqual(request.get_header("Content-length"), str(len(body)))
                self.assertIn(b'name="d_archiv"; filename="namedF.tgz"', body)
                self.assertIn(b'name="f_archiv"; filename="full.tgz"', body)
            return response

        for replies, error, methods in (
            ([uploading, uploading, queued, queued, succeeded, {"ok": True}], None,
             ["POST", "PUT", "POST", "GET", "GET", "DELETE"]),
            ([queued, succeeded, {"ok": True}], None, ["POST", "GET", "DELETE"]),
            ([uploading, b""], "gültigem JSON", ["POST", "PUT"]),
            ([uploading, uploading, {}], "keinen Auftragsstatus", ["POST", "PUT", "POST"]),
            ([{"status": "queued"}], "Auftrags-ID", ["POST"]),
            ([queued, queued | {"status": "unbekannt"}], "unbekannten Auftragsstatus", ["POST", "GET"]),
            ([failed, failed, {"ok": True}], "M/Text-Fehler", ["POST", "GET", "DELETE"]),
            ([failed, failed, network_error], "M/Text-Fehler.*Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([succeeded, succeeded, network_error], "Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([succeeded, succeeded, b""], "gültigem JSON", ["POST", "GET", "DELETE"]),
        ):
            response.read.side_effect = [
                reply if isinstance(reply, (bytes, Exception)) else json.dumps(reply).encode() for reply in replies
            ]
            packages = iter([("LOMS_Basis", self.package)])
            with (
                self.subTest(replies=replies),
                patch.object(adapter.urllib.request, "urlopen", side_effect=receive) as http,
                patch.object(adapter.time, "sleep") as wait,
            ):
                outcome = self.assertRaisesRegex(DeliveryError, error) if error else nullcontext()
                with outcome:
                    auftrag_id = adapter.synchronize(
                        "en", "01", kuerzel="FI", projekte=["LOMS_Basis"],
                        packages=packages, idempotency_key="github-run-test-Entwicklung",
                    )
                    self.assertEqual(auftrag_id, "auftrag")
            requests = [invocation.args[0] for invocation in http.call_args_list]
            self.assertEqual([request.get_method() for request in requests], methods)
            self.assertEqual(requests[0].full_url, "https://en01.ltoma.intern/vMtextAdapter/sync")
            self.assertEqual(requests[0].get_header("Idempotency-key"), "github-run-test-Entwicklung")
            self.assertEqual(wait.call_args_list, [call(5)] if methods.count("GET") == 2 else [])

            if replies[0] == queued:
                self.assertEqual(list(packages), [("LOMS_Basis", self.package)])

    def test_upload_abort_closes_stream(self) -> None:
        """Prüft, dass bei einem Verbindungsabbruch auch der Upload-Datenstrom geschlossen wird."""

        def disconnect(request, **_kwargs) -> None:
            """Bricht nach dem ersten Dateiblock ab."""

            next(request.data)
            next(request.data)
            raise urllib.error.URLError("Verbindung abgebrochen")

        with (
            patch.object(adapter.urllib.request, "urlopen", side_effect=disconnect) as http,
            self.assertRaisesRegex(DeliveryError, "Adapteraufruf") as failure,
        ):
            adapter._upload_project("https://adapter.test/sync/auftrag", "LOMS_Basis", self.package)
        self.assertEqual(failure.exception.status, Status.ADAPTER_FAILED)
        self.assertEqual(list(http.call_args.args[0].data), [])


if __name__ == "__main__":
    unittest.main()
