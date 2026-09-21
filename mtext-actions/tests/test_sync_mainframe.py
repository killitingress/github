"""Prüft Sync-Vergleichscommits, Paketübergabe und die HTTP-Adapterschnittstelle."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import unittest
import urllib.error
import urllib.parse
import zipfile
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


def execution_reply(
    status: str,
    *,
    message: str | None = None,
    result: str | None = None,
) -> dict[str, object]:
    """Stellt die feste JSON-Struktur einer simulierten Ausführung bereit."""

    return {
        "status": status,
        "message": message,
        "result": result,
    }


def auftrag_reply(
    status: str,
    *,
    message: str | None = None,
    result: str | None = None,
) -> dict[str, object]:
    """Bettet eine simulierte Ausführung in den vollständigen Auftrag ein."""

    return {
        "auftrag_id": "test-FI",
        "archive": [],
        "execution": execution_reply(status, message=message, result=result),
    }


class SyncTests(TempDirTestCase):
    """Prüft die Sync-Regeln mit gemeinsamer Git-Historie und simuliertem Adapter."""

    def setUp(self) -> None:
        """Stellt Mandantencommit und Workflow-Umgebung für die Sync-Aufrufe bereit."""

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
            "GITHUB_RUN_ATTEMPT": "1",
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
        """Prüft Zielauswahl, belegte DELTA-Basis und FULL bei fehlender oder geänderter Zuordnung."""

        # Ereignis und Zielauswahl bestimmen den Umfang unabhängig von der Speicherung
        with (
            patch.object(sync, "letzter_sync_commit") as history,
            patch.object(sync.git, "resolve", return_value="current"),
            patch.object(sync.git, "require_ancestor") as ancestor,
            patch.object(sync.git, "changes", return_value=[]) as changes,
            patch.object(sync, "build_project_package", return_value=MagicMock()),
            patch.object(sync.adapter, "check_reachability"),
            patch.object(sync.adapter, "resume_existing", return_value=None),
            patch.object(sync.adapter, "upload", return_value={}) as transfer,
        ):
            configuration = load_test_configuration(self.repository)
            for branch, event, ziel, basis, targets in (
                ("feature/261/test", "push", "Branchstandard", "previous", ["en01"]),
                ("feature/261/test", "push", "Branchstandard", None, ["en01"]),
                ("release/261", "pull_request", "Branchstandard", None, ["fu01"]),
                ("main", "pull_request", "Branchstandard", "previous", ["fu02"]),
                ("main", "workflow_dispatch", "Beide", None, ["en02", "fu02"]),
                ("main", "workflow_dispatch", "Entwicklung", None, ["en02"]),
                ("main", "workflow_dispatch", "Branchstandard", None, ["fu02"]),
                ("feature/261/test", "workflow_dispatch", "Funktionstest", None, ["fu01"]),
            ):
                with self.subTest(branch=branch, event=event, ziel=ziel), patch.dict(os.environ, {
                    "GITHUB_REF_NAME": branch, "GITHUB_EVENT_NAME": event,
                    "MTEXT_ZIELUMGEBUNG": ziel,
                }):
                    history.reset_mock()
                    history.return_value = basis
                    changes.reset_mock()
                    result = sync.run()
                    self.assertEqual([e["umgebung"] for e in result["ergebnisse"]], targets)
                    if basis:
                        changes.assert_called_once_with(self.repository, basis, sync.git.resolve.return_value)
                    else:
                        changes.assert_not_called()
                    if event == "workflow_dispatch":
                        history.assert_not_called()
                    nachweis = json.loads(Path(result["outputs"]["nachweis_path"]).read_text())
                    self.assertEqual(set(nachweis), {"commit", "releaselinie", "umgebungen"})
                    self.assertEqual(nachweis["commit"], sync.git.resolve.return_value)
                    self.assertEqual(nachweis["umgebungen"], targets)

            # Die normale Planung lehnt eine manuelle Zielauswahl im automatischen Lauf ab.
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push", "MTEXT_ZIELUMGEBUNG": "Beide"}):
                with self.assertRaises(DeliveryError) as raised:
                    sync.ermittle_plan(self.repository, configuration)
                self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

            # Ein überholter Vergleichscommit wird vor der Übertragung zurückgewiesen.
            ancestor.side_effect = [None, DeliveryError(Status.SOURCE_FAILED, "kein Vorfahr")]
            transfer.reset_mock()
            with patch.object(sync, "letzter_sync_commit", return_value="previous"):
                with self.assertRaises(DeliveryError) as raised:
                    sync.run()
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)
            transfer.assert_not_called()

        # Der Namensindex wählt den Branch. Der erste Nachweis der Umgebung entscheidet.
        branch, umgebung, releaselinie = "feature/270/test_unterordner", "en02", "270"
        previous = "previous"
        artifacts = [
            {"id": 1, "expired": True},
            {"id": 2, "expired": False},
        ]
        nachweis = {"commit": previous, "releaselinie": releaselinie, "umgebungen": [umgebung]}
        for erwartung, aktuelle_linie in ((previous, releaselinie), (None, "271")):
            with (
                patch.object(github, "artifacts", return_value=artifacts) as listed,
                patch.object(github, "artifact_document", return_value=nachweis),
            ):
                self.assertEqual(sync.letzter_sync_commit(branch, umgebung, aktuelle_linie), erwartung)
                listed.assert_called_once_with(f"mtext-stand-{urllib.parse.quote(branch, safe='')}")

        # Der Archivinhalt wird gelesen, beim Speicherabruf wird das API-Token nicht weitergegeben.
        archive = io.BytesIO()
        filename = "mtext-stand.json"
        with zipfile.ZipFile(archive, "w") as document:
            document.writestr(filename, json.dumps(nachweis))
        response = http_reply({})
        response.read.return_value = archive.getvalue()
        location = "https://storage.test/stand.zip"
        redirect = urllib.error.HTTPError("https://github.test/artifact", 302, "Found", {"Location": location}, io.BytesIO())
        with (
            patch.object(github.urllib.request, "build_opener") as opener,
            patch.object(github.urllib.request, "urlopen", return_value=response) as download,
        ):
            opener.return_value.open.side_effect = redirect
            self.assertEqual(github.artifact_document(artifacts[1]["id"], filename), nachweis)
            self.assertEqual(download.call_args.args, (location,))

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
            patch.object(sync, "letzter_sync_commit", return_value=baseline),
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

            # eine reine Konfigurationsänderung braucht im echten DELTA keine Projektübertragung
            load_test_configuration(self.repository, mandant={"dry_run": False, "excluded_projects": ["Testdaten"]})
            git(self.repository, "add", ".github")
            git(self.repository, "commit", "-m", "Konfiguration")
            git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
            transfer.reset_mock()
            with patch.object(sync, "letzter_sync_commit", return_value=commit):
                result = sync.run()
            self.assertEqual(result["ergebnisse"][0]["projekte"], [])
            transfer.assert_not_called()

        load_test_configuration(self.repository, mandant={"dry_run": False})
        with (
            patch.object(sync, "letzter_sync_commit", return_value=baseline),
            patch.object(adapter, "check_reachability"),
            patch.object(sync, "build_project_package", return_value=self.project_package) as build,
        ):
            for status in ("processing", "succeeded"):
                replies = [execution_reply(status, result="fertig" if status == "succeeded" else None)]
                if status == "processing":
                    replies.append(execution_reply("succeeded", result="fertig"))
                replies.append({"status": "deleted"})

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
                    http_reply(execution_reply(
                        status,
                        message="M/Text-Fehler" if status == "failed" else None,
                    )),
                    http_reply({"status": "deleted"}),
                ]
                replies.extend((
                    http_reply(auftrag_reply("ready"), 201),
                    http_reply(execution_reply("processing")),
                    http_reply(execution_reply("succeeded")),
                    http_reply({"status": "deleted"}),
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
                self.assertTrue(all(
                    e.full_url.endswith("/execution") for e in requests if e.get_method() == "GET"
                ))

    def _receive_archive(self, request, **_kwargs) -> MagicMock:
        """Liest den Upload-Datenstrom und prüft seine angekündigte Länge."""

        self.response.status = 201 if request.get_method() == "POST" else 200

        if request.get_method() == "PUT":
            self.assertNotIsInstance(request.data, bytes)
            body = b"".join(request.data)
            self.assertEqual(request.get_header("Content-length"), str(len(body)))
            self.assertEqual(request.get_header("Content-type"), "application/gzip")
            self.uploaded.append(body)
        return self.response

    def test_adapter_protocol(self) -> None:
        """Prüft Anlage, Mehrfach-Upload, Verarbeitung und Fehler bis zum Löschen."""

        ready = execution_reply("ready")
        created = auftrag_reply("ready")
        processing = execution_reply("processing")
        succeeded = execution_reply("succeeded", result="M/Text-Ausgabe")
        failed = execution_reply("failed", message="M/Text-Fehler")
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
            for e in (created, uploading, processing, succeeded, {"status": "deleted"})
        ]
        self.uploaded = []
        with patch.object(adapter.urllib.request, "urlopen", side_effect=self._receive_archive) as http:
            result = adapter.upload("en01", pakete, "test-FI")
        payload = json.loads(http.call_args_list[0].args[0].data)
        self.assertEqual([e["information"]["sha256"] for e in payload["archive"]],
                         ["checksum-LOMS_Basis", "checksum-LOMS_Autonom"])
        self.assertEqual(result["result"], "M/Text-Ausgabe")
        self.assertEqual(self.uploaded, [b"LOMS_Basis", b"LOMS_Autonom"])

        for replies, error_status, methods in (
            ([created, processing, processing, succeeded, {"status": "deleted"}], None,
             ["POST", "PUT", "GET", "GET", "DELETE"]),
            ([created, b""], Status.ADAPTER_FAILED, ["POST", "PUT"]),
            ([{"execution": {"status": "ready"}}], Status.ADAPTER_FAILED, ["POST"]),
            ([created, processing, processing | {"status": "unbekannt"}], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET"]),
            ([created, failed, {"status": "deleted"}], Status.ADAPTER_FAILED, ["POST", "PUT", "DELETE"]),
            ([created, processing, failed, {"status": "deleted"}], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([created, processing, failed, network_error], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([created, processing, succeeded, network_error], Status.ADAPTER_FAILED,
             ["POST", "PUT", "GET", "DELETE"]),
            ([created, processing, succeeded, b""], Status.ADAPTER_FAILED,
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
            self.assertTrue(all(
                e.full_url.endswith("/execution") for e in requests if e.get_method() == "GET"
            ))
            self.assertEqual(wait.call_args_list, [call(5)] if methods.count("GET") == 2 else [])


if __name__ == "__main__":
    unittest.main()
