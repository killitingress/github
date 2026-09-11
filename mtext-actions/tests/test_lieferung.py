"""Prüft Vorbereitung und Bestätigung der Lieferung."""

from __future__ import annotations

import dataclasses
import json
import os
import unittest
from unittest.mock import patch

from lbs_delivery.git import LieferTag
from lbs_delivery.lieferung import _pruefe_lieferquelle, _summary, run
from lbs_delivery.process import DeliveryError, Status

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

    def test_liefer_tag_exposes_release_information(self) -> None:
        """Prüft Bestandteile, Hauptrelease und Reihenfolge eines Liefer-Tags."""

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

    def test_prepares_delta_on_bereitstellung_and_shows_previous_tag(self) -> None:
        """Prüft eine DELTA-Vorbereitung mit dem vorherigen Liefer-Tag."""

        # .106 gehört zur Lieferhistorie, die höhere .107 liegt auf einem anderen Verlauf
        git(self.repository, "tag", "-d", "r261.107")
        git(self.repository, "tag", "r261.106", "HEAD^")
        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "commit", "--allow-empty", "-m", "anderer Verlauf")
        git(self.repository, "tag", "r261.107")
        git(self.repository, "switch", "-c", "bereitstellung/261.108", self.source_sha)
        track_remote_branch(self.repository, "bereitstellung/261.108")

        # ein zusätzliches leeres Projekt macht die Texte für leere Archive sichtbar
        configuration = dataclasses.replace(
            self.configuration,
            projects=self.configuration.projects | {"Leeres_Projekt": "LEER"},
        )

        # die Vorbereitung verwendet .107 als Vorgänger auch außerhalb ihrer Historie
        _pruefe_lieferquelle(
            configuration,
            self.repository,
            LieferTag.parse("r261.108"),
            "bereitstellung/261.108",
        )
        summary = _summary(
            configuration,
            self.repository,
            LieferTag.parse("r261.108"),
            "bereitstellung/261.108",
            self.source_sha,
        )
        self.assertIn("| Branch | `bereitstellung/261.108` |", summary)
        self.assertIn("- Liefer-Tag: `r261.108`", summary)
        self.assertIn("- Lieferart: `DELTA`", summary)
        self.assertIn(f"- Commit: `{self.source_sha}`", summary)
        self.assertIn("`r261.100`", summary)
        self.assertIn("Änderungen seit `r261.107`", summary)
        self.assertNotIn("Änderungen seit `r261.106`", summary)
        self.assertIn("`D` `deleted.txt`", summary)
        self.assertIn("`A` `new.txt`", summary)
        self.assertIn("## Projektarchive", summary)
        self.assertIn("Das DELTA-Archiv enthält keine geänderten oder gelöschten Ressourcen.", summary)

        # dieselbe Berichtserzeugung bezeichnet ein leeres FULL-Archiv passend
        full_summary = _summary(
            configuration,
            self.repository,
            LieferTag.parse("r261.100"),
            "release/261",
            git(self.repository, "rev-parse", "r261.100"),
        )
        self.assertIn("Das FULL-Archiv enthält keine Ressourcendateien.", full_summary)

    def test_rejects_full_on_bereitstellung_and_mismatched_branch(self) -> None:
        """Prüft Zwischenrelease-Grenzen und die passende Branchzuordnung."""

        # Tag und Bereitstellungsbranch verwenden denselben Lieferstand
        for zwischenrelease in ("100", "108", "999"):
            with self.subTest(zwischenrelease=zwischenrelease):
                tag = LieferTag.parse(f"r260.{zwischenrelease}")
                self.assertEqual(tag, LieferTag.from_bereitstellung(f"bereitstellung/260.{zwischenrelease}"))

        # Zwischenreleases außerhalb von 100–999 scheitern vor dem Git-Zugriff
        for zwischenrelease in ("000", "099", "1000"):
            with self.subTest(zwischenrelease=zwischenrelease):
                self.assertIsNone(LieferTag.from_bereitstellung(f"bereitstellung/261.{zwischenrelease}"))
                with self.assertRaises(DeliveryError) as raised:
                    run("check", f"r261.{zwischenrelease}")
                self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        track_remote_branch(self.repository, "bereitstellung/261.100")
        with self.assertRaises(DeliveryError) as raised:
            _pruefe_lieferquelle(
                self.configuration,
                self.repository,
                LieferTag.parse("r261.100"),
                "bereitstellung/261.100",
            )
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        git(self.repository, "checkout", "release/261")
        git(self.repository, "switch", "-c", "bereitstellung/261.109")
        track_remote_branch(self.repository, "bereitstellung/261.109")
        with self.assertRaises(DeliveryError) as raised:
            _pruefe_lieferquelle(
                self.configuration,
                self.repository,
                LieferTag.parse("r261.108"),
                "bereitstellung/261.109",
            )
        self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

    def test_prepares_checkout_after_branch_advances(self) -> None:
        """Die Vorbereitung hält den Lauf-Commit bei weiterentwickeltem Branch fest."""

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
                result = run("check", "r261.108")

        # Artefakt und Vorprüfung beziehen sich auf den Checkout des Laufs
        payload = json.loads((self.root / "vorbereitung.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["sha"], self.source_sha)
        self.assertEqual(payload["issue"], 42)
        self.assertEqual(result["outputs"]["vorbereitung_name"], "lieferung-42-vorbereitungsartefakt")
        self.assertIn(f"- Commit: `{self.source_sha}`", result["summary"])

    def test_resolve_authorizes_maintainers_and_confirms_issue_artifact(self) -> None:
        """Erlaubt Maintain und Admin und bindet die Vorbereitung an das Issue."""

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
            for role in ("maintain", "admin"):
                with self.subTest(role=role):
                    with patch(
                        "lbs_delivery.lieferung.github._request",
                        side_effect=({"role_name": role}, issue, artifacts),
                    ):
                        result = run("resolve", issue=42)
                    self.assertEqual(result["status"], Status.LIEFERSTAND_ERMITTELT)

            # dieselbe Rollenprüfung gilt ohne Issue für eine Wiederholung
            reference = {"object": {"sha": self.source_sha}}
            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=({"role_name": "maintain"}, reference),
            ):
                result = run("resolve", "r261.108", issue=0)
            self.assertEqual(result["status"], Status.LIEFERSTAND_ERMITTELT)

            # dieselbe Person darf vorbereiten und freigeben
            confirmed = run("confirm", issue=42)
            self.assertEqual(confirmed["status"], Status.LIEFERUNG_BESTAETIGT)
            self.assertEqual(
                confirmed["outputs"],
                {"source_sha": self.source_sha, "liefer_tag": "r261.108"},
            )

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

    def test_rejects_invalid_or_mismatched_preparation(self) -> None:
        """Lehnt beschädigte Artefakte und ein abweichendes Freigabe-Issue ab."""

        preparation = self.root / "vorbereitung" / "vorbereitung.json"
        preparation.parent.mkdir()
        arguments = {"subcommand": "confirm", "issue": 42}
        with patch.dict(
            os.environ,
            {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                "GITHUB_ACTOR": "alice",
            },
        ):
            preparation.write_text("kein JSON", encoding="utf-8")
            with self.assertRaises(DeliveryError) as raised:
                run(**arguments)
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

            preparation.write_text(
                json.dumps(
                    {
                        "tag": "r261.109",
                        "sha": self.source_sha,
                        "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
                        "issue": 41,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(DeliveryError) as raised:
                run(**arguments)
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)


if __name__ == "__main__":
    unittest.main()
