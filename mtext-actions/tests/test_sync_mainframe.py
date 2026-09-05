"""Prüft Sync-Vergleichsstände, Paketübergabe und die HTTP-Adapterschnittstelle."""

from __future__ import annotations

import hashlib
import io
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


def http_reply(document: dict[str, object], status: int = 200):
    """Stellt JSON-Antworten und HTTP-Fehler an der simulierten Netzwerkgrenze bereit."""

    body = json.dumps(document).encode()
    if status >= 400:
        return urllib.error.HTTPError("http://adapter/sync2", status, "Fehler", {}, io.BytesIO(body))

    response = MagicMock(status=status)
    response.__enter__.return_value = response
    response.read.return_value = body
    return response


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
            "lieferart": "FULL",
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
            patch.object(sync.adapter, "check_reachability"),
            patch.object(sync.adapter, "resume_existing", return_value=None),
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

    def _capture_archives(self, _umgebung, project_archives, _idempotency_key) -> dict[str, object]:
        """Liest die erzeugten Projektinformationen während ihrer Übergabe."""

        for archives in project_archives:
            self.documents.append(json.loads(archives.information.read_text()))
            # die Information muss die Prüfsumme des jeweiligen Uploads tragen
            archive = archives.f_archiv if archives.f_archiv is not None else archives.d_archiv
            self.assertEqual(self.documents[-1]["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())

            # FULL stellt ein leeres D-Archiv für den Mainframe bereit
            if self.documents[-1]["lieferart"] == "FULL":
                self.assertTrue(archives.d_archiv.is_file())
        return {"auftrag_id": "auftrag", "result": "Geändert: beispiel.xml\nGelöscht: alt.xml"}

    def test_sync_archives(self) -> None:
        """Prüft kumulative Sync-Änderungen, FULL und das Auslassen reiner Konfigurationsänderungen."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        commit = git(self.repository, "rev-parse", "HEAD")
        self.documents = []

        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "check_reachability"),
            patch.object(adapter, "resume_existing", return_value=None),
            patch.object(adapter, "synchronize", side_effect=self._capture_archives) as transfer,
        ):
            for event in ("push", "workflow_dispatch"):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event}):
                    result = sync.run()
            self.assertEqual([e["lieferart"] for e in self.documents], ["DELTA", "FULL"])
            self.assertEqual(self.documents[0]["scope"]["von"]["commit"], baseline)
            self.assertEqual(self.documents[0]["scope"]["bis"]["commit"], commit)
            self.assertIn(["M", "baseline.txt"], self.documents[0]["elemente"])
            self.assertNotIn("von", self.documents[1]["scope"])
            self.assertEqual(
                result["ergebnisse"][0]["result"],
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

    def _receive_archive(self, request, **_kwargs) -> MagicMock:
        """Liest den Upload-Datenstrom und prüft seine angekündigte Länge."""

        if request.get_method() == "PUT":
            self.assertNotIsInstance(request.data, bytes)
            body = b"".join(request.data)
            self.assertEqual(request.get_header("Content-length"), str(len(body)))
            self.assertEqual(request.get_header("Content-type"), "application/gzip")
            self.uploaded.append(body)
        return self.response

    def test_adapter_protocol(self) -> None:
        """Prüft Anlage, Archivupload, Verarbeitung und Fehler bis zum Löschen."""

        ready = {"auftrag_id": "auftrag", "status": "ready"}
        processing = ready | {"status": "processing"}
        succeeded = ready | {"status": "succeeded", "result": {"geaendert": ["beispiel.xml"]}}
        failed = ready | {"status": "failed", "message": "M/Text-Fehler"}
        network_error = urllib.error.URLError("Verbindung abgebrochen")
        self.response = http_reply({})

        for replies, error, methods in (
            ([ready, processing, processing, succeeded, {"status": "succeeded"}], None,
             ["POST", "PUT", "GET", "GET", "DELETE"]),
            ([processing, succeeded, {"status": "succeeded"}], None, ["POST", "GET", "DELETE"]),
            ([ready, b""], "gültigem JSON", ["POST", "PUT"]),
            ([{"status": "ready"}], "Auftrags-ID", ["POST"]),
            ([processing, processing | {"status": "unbekannt"}], "unbekannten Auftragsstatus", ["POST", "GET"]),
            ([processing, failed, {"status": "succeeded"}], "M/Text-Fehler", ["POST", "GET", "DELETE"]),
            ([processing, failed, network_error], "M/Text-Fehler.*Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([processing, succeeded, network_error], "Adapteraufruf", ["POST", "GET", "DELETE"]),
            ([processing, succeeded, b""], "gültigem JSON", ["POST", "GET", "DELETE"]),
        ):
            self.response.read.side_effect = [
                e if isinstance(e, (bytes, Exception)) else json.dumps(e).encode() for e in replies
            ]
            project_archives = [self.project_archives]
            self.uploaded = []
            with (
                self.subTest(replies=replies),
                patch.object(adapter.urllib.request, "urlopen", side_effect=self._receive_archive) as http,
                patch.object(adapter.time, "sleep") as wait,
            ):
                outcome = self.assertRaisesRegex(DeliveryError, error) if error else nullcontext()
                with outcome:
                    adapter_result = adapter.synchronize(
                        "en01", project_archives, "github-run-test-en01",
                    )
                    self.assertEqual(adapter_result["auftrag_id"], "auftrag")
                    self.assertEqual(adapter_result["result"], succeeded["result"])
            requests = [e.args[0] for e in http.call_args_list]
            payload = json.loads(requests[0].data)
            self.assertEqual(payload["mandant"], "FI")
            self.assertEqual(payload["archive"][0]["name"], "full.tgz")
            self.assertEqual(payload["archive"][0]["information"], json.loads(self.project_archives.information.read_text()))
            self.assertTrue(all(e == b"F-Archiv" for e in self.uploaded))
            self.assertEqual([e.get_method() for e in requests], methods)
            self.assertEqual(requests[0].full_url, "http://en01.ltoma.intern/vMtextAdapter/sync2")
            self.assertEqual(requests[0].get_header("Idempotency-key"), "github-run-test-en01")
            self.assertEqual(wait.call_args_list, [call(5)] if methods.count("GET") == 2 else [])

    def test_delta_job_uploads_multiple_archives(self) -> None:
        """Prüft einen DELTA-Auftrag mit Informationen und einem PUT je Archiv."""

        archives_by_project = []
        for project in ("LOMS_Basis", "LOMS_Autonom"):
            information = self.root / f"_INFO_FI-{project}.json"
            information.write_text(json.dumps({
                "projekt": project,
                "lieferart": "DELTA",
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
        succeeded = ready | {"status": "succeeded", "result": "M/Text-Output"}
        self.response = http_reply({})
        self.response.read.side_effect = [
            json.dumps(e).encode()
            for e in (ready, uploading, processing, succeeded, {"status": "succeeded"})
        ]
        self.uploaded = []

        with patch.object(adapter.urllib.request, "urlopen", side_effect=self._receive_archive) as http:
            result = adapter.synchronize(
                "en01", archives_by_project, "github-run-test-Entwicklung",
            )

        payload = json.loads(http.call_args_list[0].args[0].data)
        self.assertEqual([e["information"]["sha256"] for e in payload["archive"]],
                         ["checksum-LOMS_Basis", "checksum-LOMS_Autonom"])
        self.assertEqual(result, {"auftrag_id": "auftrag", "result": "M/Text-Output"})
        self.assertEqual([e.args[0].get_method() for e in http.call_args_list], [
            "POST", "PUT", "PUT", "GET", "DELETE",
        ])
        self.assertEqual(self.uploaded, [b"LOMS_Basis", b"LOMS_Autonom"])


    def test_resumes_existing_job(self) -> None:
        """Übernimmt laufende und erfolgreiche Aufträge ohne Archivbau oder POST."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        self.enterContext(patch.object(github, "last_sync_commit", return_value=baseline))
        self.enterContext(patch.object(adapter, "check_reachability"))
        build = self.enterContext(patch.object(sync, "build_project_archives", return_value=self.project_archives))

        for status in ("processing", "succeeded"):
            replies = [{"auftrag_id": "alt", "status": status, "result": "fertig"}]
            if status == "processing":
                replies.append({"auftrag_id": "alt", "status": "succeeded", "result": "fertig"})
            replies.append({"status": "succeeded"})

            # den echten Sync-Einstieg gegen den vorhandenen Adapterauftrag ausführen
            with self.subTest(status=status), patch.object(
                adapter.urllib.request, "urlopen", side_effect=[http_reply(e) for e in replies],
            ) as http:
                result = sync.run()

            # Projektbezug und Ergebnis bleiben auch ohne neue Archive erhalten
            build.assert_not_called()
            self.assertEqual(result["ergebnisse"][0]["projekte"], ["LOMS_Basis"])
            self.assertEqual(result["ergebnisse"][0]["result"], "fertig")
            self.assertEqual([e.args[0].get_method() for e in http.call_args_list],
                             ["GET", "GET", "DELETE"] if status == "processing" else ["GET", "DELETE"])

    def test_starts_new_job(self) -> None:
        """Startet bei fehlendem Auftrag oder nach dem Aufräumen mit neuen Archiven."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        self.enterContext(patch.object(github, "last_sync_commit", return_value=baseline))
        self.enterContext(patch.object(adapter, "check_reachability"))
        build = self.enterContext(patch.object(sync, "build_project_archives", return_value=self.project_archives))

        for status in (None, "ready", "uploading", "failed"):
            replies = [http_reply({}, 404)] if status is None else [
                http_reply({"auftrag_id": "alt", "status": status}), http_reply({"status": "succeeded"}),
            ]
            replies.extend(http_reply(e) for e in (
                {"auftrag_id": "neu", "status": "ready"},
                {"auftrag_id": "neu", "status": "succeeded"}, {"status": "succeeded"},
            ))

            # der Neubau folgt erst auf die Suche und gegebenenfalls das Löschen
            build.reset_mock()
            with self.subTest(status=status), patch.object(adapter.urllib.request, "urlopen", side_effect=replies) as http:
                result = sync.run()

            build.assert_called_once()
            requests = [e.args[0] for e in http.call_args_list]
            self.assertEqual([e.get_method() for e in requests],
                             ["GET"] + (["DELETE"] if status else []) + ["POST", "PUT", "DELETE"])
            post = next(e for e in requests if e.get_method() == "POST")
            self.assertEqual(post.get_header("Idempotency-key"), requests[0].get_header("Idempotency-key"))
            self.assertEqual(result["ergebnisse"][0]["auftrag_id"], "neu")

    def test_delete_conflict_finishes_without_restart(self) -> None:
        """Wertet Erfolg und Fehler nach DELETE 409 aus, ohne erneut zu starten."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        self.enterContext(patch.object(github, "last_sync_commit", return_value=baseline))
        self.enterContext(patch.object(adapter, "check_reachability"))
        build = self.enterContext(patch.object(sync, "build_project_archives", return_value=self.project_archives))

        for status in ("succeeded", "failed"):
            replies = [
                http_reply({"auftrag_id": "alt", "status": "uploading"}),
                http_reply({"message": "processing"}, 409),
                http_reply({"auftrag_id": "alt", "status": status, "message": "M/Text-Fehler"}),
                http_reply({"status": "succeeded"}),
            ]

            # zwischen Suche und Löschen ist die Verarbeitung gestartet und abgeschlossen
            with self.subTest(status=status), patch.object(adapter.urllib.request, "urlopen", side_effect=replies) as http:
                outcome = self.assertRaisesRegex(DeliveryError, "M/Text-Fehler") if status == "failed" else nullcontext()
                with outcome:
                    result = sync.run()
                    self.assertEqual(result["ergebnisse"][0]["auftrag_id"], "alt")

            # insbesondere ein inzwischen fehlgeschlagener Auftrag erzeugt keinen neuen POST
            build.assert_not_called()
            self.assertEqual([e.args[0].get_method() for e in http.call_args_list], ["GET", "DELETE", "GET", "DELETE"])



if __name__ == "__main__":
    unittest.main()
