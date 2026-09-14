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
from lbs_delivery.project_packages import ProjectPackage
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
            "GITHUB_SERVER_URL": "https://github.test",
            "GITHUB_TOKEN": "test-token",
            "MTEXT_PREVIOUS_COMMIT": "before",
        }))
        information = {
            "projekt": "LOMS_Basis",
            "lieferart": "FULL",
            "scope": {"bis": {"referenz": "release/261", "commit": "current"}},
            "sha256": "checksum",
        }
        self.project_package = ProjectPackage(information, self.root / "full.tgz")
        self.project_package.archive.write_bytes(b"F-Archiv")


    def test_run_command(self) -> None:
        """Prüft Erstlauf, DELTA-Basis, Linienwechsel, manuelles FULL und überholte Läufe."""

        with (
            patch.object(github, "_request") as history,
            patch.object(sync.git, "resolve", return_value="current"),
            patch.object(sync.git, "require_ancestor") as ancestor,
            patch.object(sync.git, "changes", return_value=[]) as changes,
            patch.object(sync.git, "execute") as read_git,
            patch.object(sync, "build_project_package", return_value=MagicMock()) as build_package,
            patch.object(sync.adapter, "check_reachability") as check_reachability,
            patch.object(sync.adapter, "resume_existing", return_value=None),
            patch.object(sync.adapter, "upload", return_value={}) as transfer,
        ):
            adapter_steps = []
            check_reachability.side_effect = lambda ziel: adapter_steps.append(("check", ziel))
            build_package.side_effect = lambda *args, **kwargs: (
                adapter_steps.append(("build", args[2])) or MagicMock()
            )

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
                read_git.side_effect = lambda _source, command, *_arguments: (
                    json.dumps({"mandant": {"releaselinie": old_line}}).encode()
                    if command == "show" else b"base"
                )
                transfer.reset_mock()
                build_package.reset_mock()
                ancestor.reset_mock()
                changes.reset_mock()
                adapter_steps.clear()
                with self.subTest(branch=branch, event=event, commits=commits), patch.dict(os.environ, {
                    "GITHUB_REF_NAME": branch, "GITHUB_EVENT_NAME": event,
                }):
                    result = sync.run()
                    self.assertEqual([e["umgebung"] for e in result["ergebnisse"]], targets)
                    self.assertEqual(result["outputs"], {})
                    self.assertIn(f"/tree/current", result["summary"])
                    if base:
                        self.assertIn(f"/compare/{base}..current", result["summary"])
                    else:
                        self.assertNotIn("/compare/", result["summary"])
                    self.assertEqual(history.call_count, len(commits))
                    branch_check = call(self.repository, "current", f"refs/remotes/origin/{branch}")
                    self.assertEqual(ancestor.call_args_list.count(branch_check), 1)

                    if branch == "main" and event == "push":
                        self.assertIn("event=push", history.call_args_list[0].kwargs["url"])
                        reference = f"{commits[0] or 'before'}:{sync.config.MANDANT_CONFIG_PATH}"
                        self.assertIn(call(self.repository, "show", reference), read_git.call_args_list)

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
                        project_count = len(load_test_configuration(self.repository).projects)
                        self.assertEqual(build_package.call_count, project_count * 2)
                        self.assertEqual(adapter_steps[:2], [("check", e) for e in targets])

            # der erste echte Lauf nach einem Dry Run wird zum vollständigen Abgleich
            history.side_effect = [{"workflow_runs": [{"head_sha": "previous"}]}]
            read_git.reset_mock()
            read_git.side_effect = lambda _source, command, *_arguments: (
                json.dumps({"mandant": {"releaselinie": "270", "dry_run": True}}).encode()
                if command == "show" else b"base"
            )
            changes.reset_mock()
            with patch.dict(os.environ, {
                "GITHUB_REF_NAME": "feature/261/test", "GITHUB_EVENT_NAME": "push",
            }):
                sync.run()
            changes.assert_not_called()

            history.side_effect = [{"workflow_runs": [{"head_sha": "previous"}]}]
            ancestor.side_effect = [None, DeliveryError(Status.SOURCE_FAILED, "kein Vorfahr")]
            transfer.reset_mock()
            with self.assertRaises(DeliveryError) as raised:
                sync.run()
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)
            transfer.assert_not_called()

    def _capture_packages(self, _umgebung, pakete, _auftrag_id) -> dict[str, object]:
        """Prüft Informations-Dokumente und Archive während ihrer Übergabe."""

        for paket in pakete:
            self.documents.append(paket.information)
            # die Information muss die Prüfsumme des jeweiligen Uploads tragen
            self.assertEqual(
                self.documents[-1]["sha256"], hashlib.sha256(paket.archive.read_bytes()).hexdigest(),
            )
        return {"auftrag_id": "auftrag", "result": "Geändert: beispiel.xml\nGelöscht: alt.xml"}

    def test_sync_packages(self) -> None:
        """Prüft Paketübergabe, Dry Run, Konfigurationsänderungen und Adapteraufträge."""

        baseline = git(self.repository, "rev-parse", "r261.100")
        commit = git(self.repository, "rev-parse", "HEAD")
        self.documents = []

        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "check_reachability") as reachability,
            patch.object(adapter, "resume_existing", return_value=None) as resume,
            patch.object(adapter, "upload", side_effect=self._capture_packages) as transfer,
        ):
            for event in ("push", "workflow_dispatch"):
                with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event}):
                    result = sync.run()
                if event == "push":
                    self.assertIn(f"/compare/{baseline}..{commit}", result["summary"])
                else:
                    self.assertIn(f"/tree/{commit}", result["summary"])
                    self.assertNotIn("/compare/", result["summary"])
            self.assertEqual([e["lieferart"] for e in self.documents], ["DELTA", "FULL"])
            self.assertEqual(self.documents[0]["scope"]["von"]["commit"], baseline)
            self.assertEqual(self.documents[0]["scope"]["bis"]["commit"], commit)
            self.assertTrue(all("elemente" not in e for e in self.documents))
            self.assertNotIn("von", self.documents[1]["scope"])
            ergebnis_path = self.root / "mtext-ergebnis.txt"
            self.assertEqual(result["outputs"]["ergebnis_path"], str(ergebnis_path))
            self.assertIn("Geändert: beispiel.xml\nGelöscht: alt.xml", ergebnis_path.read_text())
            self.assertNotIn("Geändert: beispiel.xml", result["summary"])
            self.assertNotIn("result", result["ergebnisse"][0])
            self.assertIn("Laufartefakt `mtext-ergebnis`", result["summary"])

            # Dry Run prüft die Erreichbarkeit und baut Pakete ohne Adapterauftrag
            load_test_configuration(self.repository, mandant={"dry_run": True})
            reachability.reset_mock()
            resume.reset_mock()
            transfer.reset_mock()
            result = sync.run()
            self.assertEqual(result["status"], Status.ADAPTER_SKIPPED)
            self.assertEqual(result["ergebnisse"][0]["auftrag_id"], "test-FI")
            self.assertNotIn("result", result["ergebnisse"][0])
            self.assertIn("Dry Run", ergebnis_path.read_text())
            reachability.assert_called_once()
            resume.assert_not_called()
            transfer.assert_not_called()

            git(self.repository, "add", ".github")
            git(self.repository, "commit", "-m", "Konfiguration")
            git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
            transfer.reset_mock()
            with patch.object(github, "last_sync_commit", return_value=commit):
                result = sync.run()
            self.assertEqual(result["ergebnisse"][0]["projekte"], [])
            transfer.assert_not_called()

        load_test_configuration(self.repository, mandant={"dry_run": False})
        with (
            patch.object(github, "last_sync_commit", return_value=baseline),
            patch.object(adapter, "check_reachability"),
            patch.object(sync, "build_project_package", return_value=self.project_package) as build,
        ):
            for status in ("processing", "succeeded"):
                replies = [{"auftrag_id": "test-FI", "status": status, "result": "fertig"}]
                if status == "processing":
                    replies.append({"auftrag_id": "test-FI", "status": "succeeded", "result": "fertig"})
                replies.append({"status": "succeeded"})

                with self.subTest(resume=status), patch.object(
                    adapter.urllib.request, "urlopen", side_effect=[http_reply(e) for e in replies],
                ) as http:
                    result = sync.run()

                build.assert_not_called()
                self.assertIn("fertig", ergebnis_path.read_text())
                self.assertEqual([e.args[0].get_method() for e in http.call_args_list],
                                 ["GET", "GET", "DELETE"] if status == "processing" else ["GET", "DELETE"])

            for status in (None, "ready", "uploading", "failed"):
                replies = [http_reply({}, 404)] if status is None else [
                    http_reply({"auftrag_id": "test-FI", "status": status}),
                    http_reply({"status": "succeeded"}),
                ]
                replies.extend(http_reply(e) for e in (
                    {"auftrag_id": "test-FI", "status": "ready"},
                    {"auftrag_id": "test-FI", "status": "processing"},
                    {"auftrag_id": "test-FI", "status": "succeeded"}, {"status": "succeeded"},
                ))

                build.reset_mock()
                with self.subTest(start=status), patch.object(
                    adapter.urllib.request, "urlopen", side_effect=replies,
                ) as http:
                    result = sync.run()

                build.assert_called_once()
                requests = [e.args[0] for e in http.call_args_list]
                self.assertEqual([e.get_method() for e in requests],
                                 ["GET"] + (["DELETE"] if status else []) + ["POST", "PUT", "GET", "DELETE"])
                self.assertEqual(result["ergebnisse"][0]["auftrag_id"], "test-FI")

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
        """Prüft Anlage, Mehrfach-Upload, Verarbeitung und Fehler bis zum Löschen."""

        ready = {"auftrag_id": "test-FI", "status": "ready"}
        processing = ready | {"status": "processing"}
        succeeded = ready | {"status": "succeeded", "result": {"geaendert": ["beispiel.xml"]}}
        failed = ready | {"status": "failed", "message": "M/Text-Fehler"}
        network_error = urllib.error.URLError("Verbindung abgebrochen")
        self.response = http_reply({})

        pakete = []
        for project in ("LOMS_Basis", "LOMS_Autonom"):
            information = {
                "projekt": project,
                "lieferart": "DELTA",
                "scope": {
                    "von": {"referenz": "release/261", "commit": "before"},
                    "bis": {"referenz": "release/261", "commit": "current"},
                },
                "sha256": f"checksum-{project}",
            }
            archive = self.root / f"{project}D.tgz"
            archive.write_bytes(project.encode())
            pakete.append(ProjectPackage(information, archive))

        uploading = ready | {"status": "uploading"}
        self.response.read.side_effect = [
            json.dumps(e).encode()
            for e in (ready, uploading, processing, succeeded | {"result": "M/Text-Output"}, {"status": "succeeded"})
        ]
        self.uploaded = []
        with patch.object(adapter.urllib.request, "urlopen", side_effect=self._receive_archive) as http:
            result = adapter.upload("en01", pakete, "test-FI")
        payload = json.loads(http.call_args_list[0].args[0].data)
        self.assertEqual([e["information"]["sha256"] for e in payload["archive"]],
                         ["checksum-LOMS_Basis", "checksum-LOMS_Autonom"])
        self.assertEqual(result["result"], "M/Text-Output")
        self.assertEqual(self.uploaded, [b"LOMS_Basis", b"LOMS_Autonom"])

        for replies, error_status, methods in (
            ([ready, processing, processing, succeeded, {"status": "succeeded"}], None,
             ["POST", "PUT", "GET", "GET", "DELETE"]),
            ([ready, b""], Status.ADAPTER_FAILED, ["POST", "PUT"]),
            ([{"status": "ready"}], Status.ADAPTER_FAILED, ["POST"]),
            ([ready, processing, processing | {"status": "unbekannt"}], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET"]),
            ([ready, failed, {"status": "succeeded"}], Status.ADAPTER_FAILED, ["POST", "PUT", "DELETE"]),
            ([ready, processing, failed, {"status": "succeeded"}], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([ready, processing, failed, network_error], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([ready, processing, succeeded, network_error], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([ready, processing, succeeded, b""], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
        ):
            self.response.read.side_effect = [
                e if isinstance(e, (bytes, Exception)) else json.dumps(e).encode() for e in replies
            ]
            pakete = [self.project_package]
            self.uploaded = []
            with (
                self.subTest(replies=replies),
                patch.object(adapter.urllib.request, "urlopen", side_effect=self._receive_archive) as http,
                patch.object(adapter.time, "sleep") as wait,
            ):
                outcome = self.assertRaises(DeliveryError) if error_status else nullcontext()
                with outcome:
                    adapter_result = adapter.upload(
                        "en01", pakete, "test-FI",
                    )
                    self.assertEqual(adapter_result["auftrag_id"], "test-FI")
                    self.assertEqual(adapter_result["result"], succeeded["result"])
                if error_status:
                    self.assertEqual(outcome.exception.status, error_status)
            requests = [e.args[0] for e in http.call_args_list]
            payload = json.loads(requests[0].data)
            self.assertNotIn("mandant", payload)
            self.assertEqual(payload["archive"][0]["name"], "full.tgz")
            self.assertEqual(payload["archive"][0]["information"], self.project_package.information)
            self.assertTrue(all(e == b"F-Archiv" for e in self.uploaded))
            self.assertEqual([e.get_method() for e in requests], methods)
            self.assertEqual(requests[0].full_url, "http://en01.ltoma.intern/vMtextAdapter/sync2/test-FI")
            self.assertEqual(wait.call_args_list, [call(5)] if methods.count("GET") == 2 else [])


if __name__ == "__main__":
    unittest.main()
