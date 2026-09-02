"""Prüft Sync-Vergleichsstände, Paketübergabe und die HTTP-Adapterschnittstelle."""

from __future__ import annotations

import hashlib
import json
import os
import unittest
import urllib.error
from contextlib import nullcontext
from unittest.mock import MagicMock, call, patch

from lbs_delivery import adapter, github, sync
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.project_archives import ProjectArchives
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
        self.project_archives = ProjectArchives(
            self.root / "_INFO_FI-LOMS_Basis.json", self.root / "namedF.tgz", self.root / "full.tgz",
        )
        self.project_archives.information.write_text(json.dumps({
            "projekt": "LOMS_Basis",
            "scope": {"bis": {"referenz": "release/261", "commit": "current"}},
            "elemente": [["A", "beispiel.xml"]],
            "sha256": "checksum",
        }))
        self.project_archives.d_archiv.write_bytes(b"D-Archiv")
        self.project_archives.f_archiv.write_bytes(b"F-Archiv")

    def test_run_command(self) -> None:
        """Prüft Erstlauf, DELTA-Basis, Linienwechsel, manuelles FULL und überholte Läufe."""

        with (
            patch.object(github, "request") as history,
            patch.object(sync.git, "resolve", return_value="current"),
            patch.object(sync.git, "require_ancestor") as ancestor,
            patch.object(sync.git, "changes", return_value=[]) as changes,
            patch.object(sync.git, "execute") as read_git,
            patch.object(sync, "build_project_archives", return_value=MagicMock()) as build_archives,
            patch.object(sync.adapter, "synchronize", return_value={}) as transfer,
        ):
            # Der letzte Erfolg bestimmt das DELTA. Ein manueller Lauf bestätigt
            # keinen ausstehenden Linienwechsel für beide Umgebungen.
            for branch, event, commits, old_line, base, targets in (
                ("feature/261/test", "push", ["previous"], "270", "previous", ["en01"]),
                ("feature/261/test", "push", [None], "270", "base", ["en01"]),
                ("release/261", "push", [None], "270", None, ["fu01"]),
                ("main", "push", ["previous", "previous"], "270", "previous", ["fu02"]),
                ("main", "push", ["current"], "261", None, ["en02", "fu02"]),
                ("main", "push", [None], "261", None, ["en02", "fu02"]),
                ("main", "push", ["current", "current"], "270", "current", ["fu02"]),
                ("main", "workflow_dispatch", [], "261", None, ["fu02"]),
                ("feature/261/test", "workflow_dispatch", [], "270", None, ["en01"]),
            ):
                history.reset_mock()
                history.side_effect = [
                    {"workflow_runs": [{"head_sha": e}] if e else []} for e in commits
                ]
                read_git.reset_mock()
                read_git.return_value = (
                    json.dumps({"mandant": {"releaselinie": old_line}}).encode() if branch == "main" else b"base"
                )
                transfer.reset_mock()
                build_archives.reset_mock()
                ancestor.reset_mock()
                changes.reset_mock()
                with self.subTest(branch=branch, event=event, commits=commits), patch.dict(os.environ, {
                    "GITHUB_REF_NAME": branch, "GITHUB_EVENT_NAME": event,
                }):
                    result = sync.run()
                    self.assertEqual([e["umgebung"] for e in result["ergebnisse"]], targets)
                    self.assertEqual(history.call_count, len(commits))
                    branch_check = call(self.repository, "current", f"refs/remotes/origin/{branch}")
                    self.assertEqual(ancestor.call_args_list.count(branch_check), 1)

                    if branch == "main" and event == "push":
                        self.assertIn("event=push", history.call_args_list[0].kwargs["url"])
                        reference = f"{commits[0] or 'before'}:{sync.config.MANDANT_CONFIG_PATH}"
                        read_git.assert_called_once_with(self.repository, "show", reference)

                    if base == "base":
                        read_git.assert_called_with(
                            self.repository, "merge-base", "current", "refs/remotes/origin/release/261",
                        )

                    if base:
                        changes.assert_called_once_with(self.repository, base, "current")
                    else:
                        changes.assert_not_called()

                    if len(targets) == 2:
                        self.assertEqual(transfer.call_count, 2)
                        self.assertEqual(build_archives.call_count, len(load_test_configuration(self.repository).projects))

            history.side_effect = [{"workflow_runs": [{"head_sha": "previous"}]}]
            ancestor.side_effect = [None, DeliveryError(Status.SOURCE_FAILED, "kein Vorfahr")]
            transfer.reset_mock()
            with self.assertRaisesRegex(DeliveryError, "Der Lauf ist überholt"):
                sync.run()
            transfer.assert_not_called()

    def test_sync_archives(self) -> None:
        """Prüft kumulative Sync-Änderungen, FULL und das Auslassen reiner Konfigurationsänderungen."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        commit = git(self.repository, "rev-parse", "HEAD")
        documents = []

        def capture_archives(_umgebung, project_archives, _idempotency_key) -> dict[str, object]:
            """Liest die erzeugten Projektinformationen während ihrer Übergabe."""

            for archives in project_archives:
                documents.append(json.loads(archives.information.read_text()))
                # die Information muss die Prüfsumme des jeweiligen Uploads tragen
                archive = archives.f_archiv if archives.f_archiv is not None else archives.d_archiv
                self.assertEqual(documents[-1]["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())

                # FULL stellt ein leeres D-Archiv für den Mainframe bereit
                if "von" not in documents[-1]["scope"]:
                    self.assertTrue(archives.d_archiv.is_file())
            return {"auftrag_id": "auftrag", "ergebnis": "Geändert: beispiel.xml\nGelöscht: alt.xml"}

        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "synchronize", side_effect=capture_archives) as transfer,
        ):
            for event in ("push", "workflow_dispatch"):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event}):
                    result = sync.run()
            self.assertEqual(documents[0]["scope"]["von"]["commit"], baseline)
            self.assertEqual(documents[0]["scope"]["bis"]["commit"], commit)
            self.assertIn(["M", "baseline.txt"], documents[0]["elemente"])
            self.assertNotIn("von", documents[1]["scope"])
            self.assertEqual(
                result["ergebnisse"][0]["ergebnis"],
                "Geändert: beispiel.xml\nGelöscht: alt.xml",
            )
            self.assertIn("Geändert: beispiel.xml\nGelöscht: alt.xml", result["summary"])

            git(self.repository, "add", ".github")
            git(self.repository, "commit", "-m", "Konfiguration")
            git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
            transfer.reset_mock()
            with patch.object(github, "last_sync_commit", return_value=commit):
                result = sync.run()
            self.assertEqual(result["ergebnisse"][0]["projekte"], [])
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
                self.assertEqual(payload["kuerzel"], "FI")
                self.assertEqual(payload["auftragsart"], "FULL")
                self.assertEqual(payload["archive"][0]["name"], "full.tgz")
                self.assertEqual(payload["archive"][0]["information"]["projekt"], "LOMS_Basis")
                self.assertEqual(payload["archive"][0]["information"]["sha256"], "checksum")

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
                e if isinstance(e, (bytes, Exception)) else json.dumps(e).encode() for e in replies
            ]
            project_archives = iter([self.project_archives])
            with (
                self.subTest(replies=replies),
                patch.object(adapter.urllib.request, "urlopen", side_effect=receive) as http,
                patch.object(adapter.time, "sleep") as wait,
            ):
                outcome = self.assertRaisesRegex(DeliveryError, error) if error else nullcontext()
                with outcome:
                    adapter_result = adapter.synchronize(
                        "en01", project_archives, "github-run-test-en01",
                    )
                    self.assertEqual(adapter_result["auftrag_id"], "auftrag")
                    self.assertEqual(adapter_result["ergebnis"], succeeded["ergebnis"])
            requests = [e.args[0] for e in http.call_args_list]
            self.assertEqual([e.get_method() for e in requests], methods)
            self.assertEqual(requests[0].full_url, "http://en01.ltoma.intern/vMtextAdapter/sync")
            self.assertEqual(requests[0].get_header("Idempotency-key"), "github-run-test-en01")
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
            adapter._upload_archive("http://adapter.test/sync/auftrag", self.project_archives.f_archiv)
        self.assertEqual(failure.exception.status, Status.ADAPTER_FAILED)
        self.assertEqual(list(http.call_args.args[0].data), [])

    def test_delta_job_uploads_multiple_archives(self) -> None:
        """Prüft einen DELTA-Auftrag mit Informationen und einem PUT je Archiv."""

        archives_by_project = []
        for project in ("LOMS_Basis", "LOMS_Autonom"):
            information = self.root / f"_INFO_FI-{project}.json"
            information.write_text(json.dumps({
                "projekt": project,
                "scope": {
                    "von": {"referenz": "release/261", "commit": "before"},
                    "bis": {"referenz": "release/261", "commit": "current"},
                },
                "elemente": [["M", "beispiel.xml"]],
                "sha256": f"checksum-{project}",
            }))
            archive = self.root / f"{project}D.tgz"
            archive.write_bytes(project.encode())
            archives_by_project.append(ProjectArchives(information, archive, None))

        ready = {"auftrag_id": "auftrag", "status": "ready"}
        uploading = ready | {"status": "uploading"}
        processing = ready | {"status": "processing"}
        succeeded = ready | {"status": "succeeded", "ergebnis": "M/Text-Output"}
        response = MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.side_effect = [
            json.dumps(e).encode()
            for e in (ready, uploading, processing, succeeded, {"ok": True})
        ]
        uploaded = []

        def receive(request, **_kwargs) -> MagicMock:
            """Merkt POST-Inhalt und unveränderte Archivuploads für die Prüfung."""

            if request.get_method() == "POST":
                payload = json.loads(request.data)
                self.assertEqual(payload["auftragsart"], "DELTA")
                self.assertEqual(len(payload["archive"]), 2)
                self.assertEqual(
                    [e["information"]["sha256"] for e in payload["archive"]],
                    ["checksum-LOMS_Basis", "checksum-LOMS_Autonom"],
                )
            elif request.get_method() == "PUT":
                uploaded.append((request.full_url, b"".join(request.data)))
            return response

        with patch.object(adapter.urllib.request, "urlopen", side_effect=receive) as http:
            result = adapter.synchronize(
                "en01", archives_by_project, "github-run-test-Entwicklung",
            )

        self.assertEqual(result, {"auftrag_id": "auftrag", "ergebnis": "M/Text-Output"})
        self.assertEqual([e.args[0].get_method() for e in http.call_args_list], [
            "POST", "PUT", "PUT", "GET", "DELETE",
        ])
        self.assertEqual([body for _url, body in uploaded], [b"LOMS_Basis", b"LOMS_Autonom"])


if __name__ == "__main__":
    unittest.main()
