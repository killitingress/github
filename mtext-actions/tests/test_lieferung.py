"""Prüft Vorbereitung und Bestätigung der Lieferung."""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

import mtext
from lbs_delivery.git import LieferTag
from lbs_delivery.lieferung import liefer_tag_fuer_branch, run
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.project_packages import previous_release_scope, project_elements, release_scope

from tests.support import TempDirTestCase, git, load_test_configuration, setup_release_repository, track_remote_branch


class LieferungTests(TempDirTestCase):
    """Prüft Liefer-Tag, Branchzuordnung, Lieferumfang und Bestätigung."""

    def setUp(self) -> None:
        """Bereitet einen noch nicht getaggten DELTA-Stand vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        git(self.repository, "tag", "-d", "r261.108")
        self.configuration = load_test_configuration(self.repository)
        self.source_sha = git(self.repository, "rev-parse", "HEAD")

    def test_liefer_tag_and_branch_rules(self) -> None:
        """Prüft Bestandteile, Reihenfolge und zulässige Lieferzweige."""

        # ein Zwischenrelease liefert seine Bestandteile und die FULL-Basis
        tag = LieferTag.parse("r261.108")
        self.assertEqual(tag.releaselinie, "261")
        self.assertEqual(tag.zwischenrelease, "108")
        self.assertFalse(tag.ist_hauptrelease)
        self.assertLess(tag, LieferTag.parse("r270.100"))

        # Tag und Bereitstellungsbranch beschreiben denselben Lieferstand
        self.assertEqual(tag, LieferTag.from_bereitstellung("bereitstellung/261.108"))
        self.assertTrue(LieferTag.parse("r261.100").ist_hauptrelease)
        self.assertIsNone(LieferTag.from_bereitstellung("anderer-branch"))
        with self.assertRaises(ValueError):
            LieferTag.parse("r261.099")

        # Lieferzweige legen den Tag ohne Benutzereingabe fest
        self.assertEqual(str(liefer_tag_fuer_branch(self.configuration, "main")), "r270.100")
        self.assertEqual(str(liefer_tag_fuer_branch(self.configuration, "release/261")), "r261.100")
        self.assertEqual(
            str(liefer_tag_fuer_branch(self.configuration, "bereitstellung/261.108")),
            "r261.108",
        )

        # .100 entsteht nicht aus einem Bereitstellungsbranch
        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_fuer_branch(self.configuration, "bereitstellung/261.100")
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        # andere Branches sind keine Lieferquelle
        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_fuer_branch(self.configuration, "feature/261/beispiel")
        self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

    def test_separates_previous_changes_from_archive_contents(self) -> None:
        """Trennt Vorrelease-Änderungen vom kumulativen DELTA-Archivinhalt."""

        # unveränderte Testhistorie vergleicht für die Information .107 und für das Archiv .100
        tag = LieferTag.parse("r261.108")
        information_scope = previous_release_scope(self.repository, tag, self.source_sha)
        paket_scope = release_scope(self.repository, tag, self.source_sha)

        # beide fachlichen Elementlisten unterscheiden sich unabhängig von ihrer Darstellung
        information_elements = project_elements(self.repository, "LOMS_Basis", information_scope)
        paket_elements = project_elements(self.repository, "LOMS_Basis", paket_scope)
        self.assertIn(["D", "transient.txt"], information_elements)
        self.assertNotIn(["M", "baseline.txt"], information_elements)
        self.assertNotIn(["D", "transient.txt"], paket_elements)
        self.assertIn(["M", "baseline.txt"], paket_elements)

    def test_resource_check_derives_delivery_scope_from_branch(self) -> None:
        """Übergibt der Ressourcenprüfung den aus dem Lieferzweig abgeleiteten Umfang."""

        with (
            patch.dict(os.environ, {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": self.configuration.repository,
                "GITHUB_REF_NAME": "bereitstellung/261.108",
            }),
            patch.object(sys, "argv", ["mtext.py", "resources", "check", "--delivery-scope"]),
            patch.object(mtext.resource_check, "run", return_value={}) as check,
        ):
            mtext.run()

        scope = check.call_args.args[0]
        self.assertEqual(scope.von[0], "r261.100")
        self.assertEqual(scope.bis, ("r261.108", self.source_sha))

    def test_prepares_checkout_after_branch_advances(self) -> None:
        """Die Vorbereitung hält den Lauf-Commit bei weiterentwickeltem Branch fest."""

        # die neue FULL-Lieferung der Releaselinie ist noch nicht gekennzeichnet
        git(self.repository, "tag", "-d", "r261.100")

        # der Remote-Branch ist weiter, der Checkout bleibt auf dem Commit des Laufs
        git(self.repository, "commit", "--allow-empty", "-m", "später")
        track_remote_branch(self.repository, "release/261")
        git(self.repository, "checkout", "--detach", self.source_sha)

        # den gestarteten Stand für die spätere Lieferung vorbereiten
        with patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(self.root),
            "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "GITHUB_REF_NAME": "release/261",
            "GITHUB_ACTOR": "alice",
            "GITHUB_API_URL": "https://github.example/api/v3",
            "GITHUB_SERVER_URL": "https://github.example",
            "GITHUB_RUN_ID": "1234",
            "GITHUB_TOKEN": "secret",
        }):
            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=(
                    None,
                    {"name": "lieferung:freigabe"},
                    {
                        "number": 42,
                        "html_url": "https://github.example/FI/mandant/issues/42",
                        "labels": [{"name": "lieferung:freigabe"}],
                    },
                ),
            ):
                result = run("check")

        # Artefakt und Vorprüfung beziehen sich auf den Checkout des Laufs
        payload = json.loads((self.root / "vorbereitung.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["sha"], self.source_sha)
        self.assertEqual(payload["tag"], "r261.100")
        self.assertEqual(payload["issue"], 42)
        self.assertEqual(result["outputs"]["vorbereitung_name"], "lieferung-42-vorbereitungsartefakt")

    def test_resolve_authorizes_and_confirms_issue_artifact(self) -> None:
        """Prüft Berechtigung und Bindung der Vorbereitung an das Issue."""

        payload = {
            "tag": "r261.108",
            "sha": self.source_sha,
            "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "issue": 42,
        }
        preparation = self.root / "vorbereitung" / "vorbereitung.json"
        preparation.parent.mkdir()
        preparation.write_text(json.dumps(payload), encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                "GITHUB_ACTOR": "alice",
                "GITHUB_API_URL": "https://github.example/api/v3",
                "GITHUB_SERVER_URL": "https://github.example",
                "GITHUB_RUN_ID": "1234",
                "GITHUB_TOKEN": "secret",
            },
        ):
            issue = {"state": "open", "labels": [{"name": "lieferung:freigabe"}]}
            artifacts = {"artifacts": [{"id": 20, "created_at": "2026-08-21T10:00:00Z", "expired": False}]}

            # resolve prüft Rolle, offenes Issue und zugeordnetes Artefakt gemeinsam
            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=({"role_name": "maintain"}, issue, artifacts),
            ):
                result = run("resolve", issue=42)
            self.assertEqual(result["status"], Status.LIEFERSTAND_ERMITTELT)

            # dieselbe Person darf vorbereiten und der gestartete Lauf wird verknüpft
            with patch("lbs_delivery.lieferung.github._request") as api:
                confirmed = run("confirm", issue=42)
            self.assertEqual(confirmed["status"], Status.LIEFERUNG_BESTAETIGT)
            self.assertEqual(
                confirmed["outputs"],
                {"source_sha": self.source_sha, "liefer_tag": "r261.108"},
            )
            api.assert_called_once()
            self.assertIn("/actions/runs/1234", api.call_args.kwargs["payload"]["body"])

            # ein nicht abgeschlossener Lauf bleibt im offenen Issue nachvollziehbar
            with patch("lbs_delivery.lieferung.github._request") as api:
                incomplete = run("incomplete", issue=42)
            self.assertEqual(incomplete["status"], Status.LIEFERUNG_NICHT_ABGESCHLOSSEN)
            api.assert_called_once()

            # Write reicht für die Freigabe nicht aus
            with patch("lbs_delivery.lieferung.github._request", return_value={"role_name": "write"}):
                with self.assertRaises(DeliveryError) as raised:
                    run("resolve", issue=42)
            self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

            # ein anderes Issue darf dasselbe Artefakt nicht übernehmen
            with self.assertRaises(DeliveryError) as raised:
                run("confirm", issue=41)
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

            # eine erfolgreiche Lieferung ergänzt und schließt das Freigabe-Issue
            with patch("lbs_delivery.lieferung.github._request") as api:
                completed = run("complete", "r261.108", issue=42)
            self.assertEqual(completed["status"], Status.LIEFERUNG_ABGESCHLOSSEN)
            self.assertEqual([e.kwargs["method"] for e in api.call_args_list], ["POST", "PATCH"])

    def test_creates_delivery_tag_from_prepared_sha(self) -> None:
        """Erstellt den Tag ohne Checkout und übernimmt ihn bei derselben SHA."""

        with patch.dict(os.environ, {"SOURCE_SHA": self.source_sha}):
            # fehlenden Tag auf der bekannten SHA anlegen
            with (
                patch("lbs_delivery.lieferung.github.tag_sha", return_value=None),
                patch("lbs_delivery.lieferung.github.create_tag") as create_tag,
            ):
                result = run("tag", "r261.108")
            self.assertEqual(result["status"], Status.LIEFERUNG_TAGGED)
            create_tag.assert_called_once_with("r261.108", self.source_sha)

            # erneuter Abschluss derselben SHA braucht keine zweite Referenz
            with (
                patch("lbs_delivery.lieferung.github.tag_sha", return_value=self.source_sha),
                patch("lbs_delivery.lieferung.github.create_tag") as create_tag,
            ):
                run("tag", "r261.108")
            create_tag.assert_not_called()

            # eine fremde Referenz darf nicht umgebogen werden
            with patch("lbs_delivery.lieferung.github.tag_sha", return_value="anderer-commit"):
                with self.assertRaises(DeliveryError) as raised:
                    run("tag", "r261.108")
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

    def test_resolves_latest_preparation_or_existing_tag(self) -> None:
        """Verwendet den neuesten geplanten Stand und erkennt Wiederholungen."""

        # die jüngste gültige Vorbereitung zählt, eine neuere abgelaufene nicht
        artifacts = {
            "artifacts": [
                {"id": 10, "created_at": "2026-08-20T10:00:00Z", "expired": False, "workflow_run": {"id": 100}},
                {"id": 20, "created_at": "2026-08-21T10:00:00Z", "expired": False, "workflow_run": {"id": 200}},
                {"id": 30, "created_at": "2026-08-22T10:00:00Z", "expired": True, "workflow_run": {"id": 300}},
            ]
        }
        arguments = {"subcommand": "resolve", "issue": 42}
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "FI/mandant",
                "GITHUB_ACTOR": "alice",
                "GITHUB_TOKEN": "secret",
                "GITHUB_API_URL": "https://github.example/api/v3",
            },
        ):
            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=(
                    {"role_name": "maintain"},
                    {"state": "open", "labels": [{"name": "lieferung:freigabe"}]},
                    artifacts,
                ),
            ):
                planned = run(**arguments)
        self.assertEqual(
            planned["outputs"],
            {
                "wiederholung": "false",
                "vorbereitung_artefakt_id": 20,
            },
        )
        self.assertEqual(planned["status"], Status.LIEFERSTAND_ERMITTELT)

        reference = {"object": {"sha": self.source_sha, "type": "commit"}}
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "FI/mandant",
                "GITHUB_ACTOR": "alice",
                "GITHUB_TOKEN": "secret",
                "GITHUB_API_URL": "https://github.example/api/v3",
            },
        ):
            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=({"role_name": "admin"}, reference),
            ):
                repeated = run("resolve", "r261.108")
        self.assertEqual(
            repeated["outputs"],
            {
                "wiederholung": "true",
                "source_sha": self.source_sha,
                "liefer_tag": "r261.108",
            },
        )
        self.assertEqual(repeated["status"], Status.LIEFERSTAND_ERMITTELT)

        # fehlender oder doppelt angegebener Lieferweg scheitert vor GitHub-Zugriffen
        for invalid in ({"issue": 0}, {"tag": "r261.108", "issue": 42}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(DeliveryError) as raised:
                    run("resolve", **invalid)
                self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

if __name__ == "__main__":
    unittest.main()
