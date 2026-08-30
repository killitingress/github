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
from lbs_delivery.project_artifacts import ProjectArtifacts
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
        self.artifacts = ProjectArtifacts(self.root / "info.json", self.root / "namedF.tgz", self.root / "full.tgz")
        self.artifacts.information.write_text(json.dumps({
            "projekt": "LOMS_Basis",
            "stand": {"bis": {"referenz": "release/261", "commit": "current"}},
            "elemente": [["A", "beispiel.xml"]],
            "sha256": {"F": "checksum"},
        }))
        self.artifacts.d_archiv.write_bytes(b"D-Archiv")
        self.artifacts.f_archiv.write_bytes(b"F-Archiv")

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

    def test_sync_archives(self) -> None:
        """Prüft kumulative Sync-Änderungen, FULL und das Auslassen reiner Konfigurationsänderungen."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        commit = git(self.repository, "rev-parse", "HEAD")
        documents = []

        def capture_artifacts(*_args, artifacts, **_kwargs) -> dict[str, object]:
            """Liest die erzeugten Projektinformationen während ihrer Übergabe."""

            for _project, project_artifacts in artifacts:
                documents.append(json.loads(project_artifacts.information.read_text()))
                if "von" not in documents[-1]["stand"]:
                    self.assertIsNone(project_artifacts.d_archiv)
            return {"auftrag_id": "auftrag", "ergebnis": "Geändert: beispiel.xml\nGelöscht: alt.xml"}

        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "synchronize", side_effect=capture_artifacts) as transfer,
        ):
            for event in ("push", "workflow_dispatch"):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event}):
                    result = sync.run(SimpleNamespace())
            self.assertEqual(documents[0]["stand"]["von"]["commit"], baseline)
            self.assertEqual(documents[0]["stand"]["bis"]["commit"], commit)
            self.assertIn(["M", "baseline.txt"], documents[0]["elemente"])
            self.assertNotIn("von", documents[1]["stand"])
            self.assertEqual([set(document["sha256"]) for document in documents], [{"D"}, {"F"}])
            self.assertEqual(
                result["synchronisationen"][0]["ergebnis"],
                "Geändert: beispiel.xml\nGelöscht: alt.xml",
            )
            self.assertIn("Geändert: beispiel.xml\nGelöscht: alt.xml", result["summary"])

            git(self.repository, "add", ".github")
            git(self.repository, "commit", "-m", "Konfiguration")
            git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
            transfer.reset_mock()
            with patch.object(github, "last_sync_commit", return_value=commit):
                result = sync.run(SimpleNamespace())
            self.assertEqual(result["synchronisationen"][0]["projekte"], [])
            transfer.assert_not_called()

    def test_adapter_protocol(self) -> None:
        """Prüft Anlage, Archivupload, Wiederaufnahme und Fehler bis zum Löschen."""

        ready = {"auftrag_id": "auftrag", "status": "ready"}
        processing = ready | {"status": "processing"}
        succeeded = ready | {"status": "succeeded", "ergebnis": {"geaendert": ["beispiel.xml"]}}
        failed = ready | {"status": "failed", "meldung": "M/Text-Fehler"}
        network_error = urllib.error.URLError("Verbindung abgebrochen")
        response = MagicMock(status=200)
        response.__enter__.return_value = response

        def receive(request, **_kwargs) -> MagicMock:
            """Prüft POST-Metadaten und liest den echten Archivdatenstrom."""

            if request.get_method() == "POST":
                payload = json.loads(request.data)
                self.assertEqual(payload["auftragsart"], "FULL")
                self.assertEqual(payload["archive"][0]["name"], "full.tgz")
                self.assertEqual(payload["archive"][0]["information"]["projekt"], "LOMS_Basis")

            if request.get_method() == "PUT":
                self.assertNotIsInstance(request.data, bytes)
                body = b"".join(request.data)
                self.assertEqual(request.get_header("Content-length"), str(len(body)))
                self.assertEqual(request.get_header("Content-type"), "application/gzip")
                self.assertEqual(body, b"F-Archiv")
                self.assertTrue(request.full_url.endswith("/archive/full.tgz"))
            return response

        for replies, error, methods in (
            ([ready, processing, processing, succeeded, {"ok": True}], None,
             ["POST", "PUT", "GET", "GET", "DELETE"]),
            ([processing, succeeded, {"ok": True}], None, ["POST", "GET", "DELETE"]),
            ([ready, b""], "gültigem JSON", ["POST", "PUT"]),
            ([{"status": "ready"}], "Auftrags-ID", ["POST"]),
            ([processing, processing | {"status": "unbekannt"}], "unbekannten Auftragsstatus", ["POST", "GET"]),
            ([processing, failed, {"ok": True}], "M/Text-Fehler", ["POST", "GET", "DELETE"]),
            ([processing, failed, network_error], "M/Text-Fehler.*Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([processing, succeeded, network_error], "Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([processing, succeeded, b""], "gültigem JSON", ["POST", "GET", "DELETE"]),
        ):
            response.read.side_effect = [
                reply if isinstance(reply, (bytes, Exception)) else json.dumps(reply).encode() for reply in replies
            ]
            artifacts = iter([("LOMS_Basis", self.artifacts)])
            with (
                self.subTest(replies=replies),
                patch.object(adapter.urllib.request, "urlopen", side_effect=receive) as http,
                patch.object(adapter.time, "sleep") as wait,
            ):
                outcome = self.assertRaisesRegex(DeliveryError, error) if error else nullcontext()
                with outcome:
                    adapter_result = adapter.synchronize(
                        "en", "01", kuerzel="FI",
                        artifacts=artifacts, idempotency_key="github-run-test-Entwicklung",
                    )
                    self.assertEqual(adapter_result["auftrag_id"], "auftrag")
                    self.assertEqual(adapter_result["ergebnis"], succeeded["ergebnis"])
            requests = [invocation.args[0] for invocation in http.call_args_list]
            self.assertEqual([request.get_method() for request in requests], methods)
            self.assertEqual(requests[0].full_url, "https://en01.ltoma.intern/vMtextAdapter/sync")
            self.assertEqual(requests[0].get_header("Idempotency-key"), "github-run-test-Entwicklung")
            self.assertEqual(wait.call_args_list, [call(5)] if methods.count("GET") == 2 else [])

    def test_upload_abort_closes_stream(self) -> None:
        """Prüft, dass bei einem Verbindungsabbruch auch der Upload-Datenstrom geschlossen wird."""

        def disconnect(request, **_kwargs) -> None:
            """Bricht nach dem ersten Dateiblock ab."""

            next(request.data)
            raise urllib.error.URLError("Verbindung abgebrochen")

        with (
            patch.object(adapter.urllib.request, "urlopen", side_effect=disconnect) as http,
            self.assertRaisesRegex(DeliveryError, "Adapteraufruf") as failure,
        ):
            adapter._upload_archive("https://adapter.test/sync/auftrag", self.artifacts.f_archiv)
        self.assertEqual(failure.exception.status, Status.ADAPTER_FAILED)
        self.assertEqual(list(http.call_args.args[0].data), [])

    def test_delta_job_uploads_multiple_archives(self) -> None:
        """Prüft einen DELTA-Auftrag mit Informationen und einem PUT je Archiv."""

        artifacts = []
        for project in ("LOMS_Basis", "LOMS_Autonom"):
            information = self.root / f"{project}.json"
            information.write_text(json.dumps({
                "projekt": project,
                "stand": {
                    "von": {"referenz": "release/261", "commit": "before"},
                    "bis": {"referenz": "release/261", "commit": "current"},
                },
                "elemente": [["M", "beispiel.xml"]],
                "sha256": {"D": f"checksum-{project}"},
            }))
            archive = self.root / f"{project}D.tgz"
            archive.write_bytes(project.encode())
            artifacts.append((project, ProjectArtifacts(information, archive, None)))

        ready = {"auftrag_id": "auftrag", "status": "ready"}
        uploading = ready | {"status": "uploading"}
        processing = ready | {"status": "processing"}
        succeeded = ready | {"status": "succeeded", "ergebnis": "M/Text-Output"}
        response = MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.side_effect = [
            json.dumps(reply).encode()
            for reply in (ready, uploading, processing, succeeded, {"ok": True})
        ]
        uploaded = []

        def receive(request, **_kwargs) -> MagicMock:
            """Merkt POST-Inhalt und unveränderte Archivuploads für die Prüfung."""

            if request.get_method() == "POST":
                payload = json.loads(request.data)
                self.assertEqual(payload["auftragsart"], "DELTA")
                self.assertEqual(len(payload["archive"]), 2)
            elif request.get_method() == "PUT":
                uploaded.append((request.full_url, b"".join(request.data)))
            return response

        with patch.object(adapter.urllib.request, "urlopen", side_effect=receive) as http:
            result = adapter.synchronize(
                "en", "01", kuerzel="FI", artifacts=iter(artifacts),
                idempotency_key="github-run-test-Entwicklung",
            )

        self.assertEqual(result, {"auftrag_id": "auftrag", "ergebnis": "M/Text-Output"})
        self.assertEqual([invocation.args[0].get_method() for invocation in http.call_args_list], [
            "POST", "PUT", "PUT", "GET", "DELETE",
        ])
        self.assertEqual([body for _url, body in uploaded], [b"LOMS_Basis", b"LOMS_Autonom"])


if __name__ == "__main__":
    unittest.main()
