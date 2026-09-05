"""Prüft Vorbereitung und Bestätigung der Lieferung."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from lbs_delivery.git import BEREITSTELLUNG_BRANCH_RE, LIEFER_TAG_RE
from lbs_delivery.lieferung import _pruefe_lieferquelle, _summary, run
from lbs_delivery.process import DeliveryError

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

        # die Vorbereitung verwendet .107 als Vorgänger auch außerhalb ihrer Historie
        _pruefe_lieferquelle(
            self.configuration,
            self.repository,
            "r261.108",
            "bereitstellung/261.108",
        )
        summary = _summary(
            self.configuration,
            self.repository,
            "r261.108",
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

    def test_rejects_full_on_bereitstellung_and_mismatched_branch(self) -> None:
        """Prüft Zwischenrelease-Grenzen und die passende Branchzuordnung."""

        # Tag und Bereitstellungsbranch verwenden denselben Lieferstand mit
        # Zwischenrelease 100–999. Ungültige Werte scheitern vor dem Git-Zugriff.
        for zwischenrelease in ("100", "108", "999"):
            for pattern, value in (
                (LIEFER_TAG_RE, f"r260.{zwischenrelease}"),
                (BEREITSTELLUNG_BRANCH_RE, f"bereitstellung/260.{zwischenrelease}"),
            ):
                with self.subTest(value=value):
                    match = pattern.fullmatch(value)
                    self.assertIsNotNone(match)
                    self.assertEqual(match.groupdict(), {"releaselinie": "260", "zwischenrelease": zwischenrelease})

        for zwischenrelease in ("000", "099", "1000"):
            with self.subTest(zwischenrelease=zwischenrelease):
                self.assertIsNone(BEREITSTELLUNG_BRANCH_RE.fullmatch(f"bereitstellung/261.{zwischenrelease}"))
                with self.assertRaisesRegex(DeliveryError, "ungültiges Format des Liefer-Tags"):
                    _pruefe_lieferquelle(
                        self.configuration,
                        self.repository,
                        f"r261.{zwischenrelease}",
                        "release/261",
                    )

        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        track_remote_branch(self.repository, "bereitstellung/261.100")
        with self.assertRaisesRegex(DeliveryError, r"\.100 entsteht"):
            _pruefe_lieferquelle(
                self.configuration,
                self.repository,
                "r261.100",
                "bereitstellung/261.100",
            )

        git(self.repository, "checkout", "release/261")
        git(self.repository, "switch", "-c", "bereitstellung/261.109")
        track_remote_branch(self.repository, "bereitstellung/261.109")
        with self.assertRaisesRegex(DeliveryError, "passt nicht zum Liefer-Tag"):
            _pruefe_lieferquelle(
                self.configuration,
                self.repository,
                "r261.108",
                "bereitstellung/261.109",
            )

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
        }):
            result = run("check", "r261.108")

        # Artefakt und Vorprüfung beziehen sich auf den Checkout des Laufs
        payload = json.loads((self.root / "vorbereitung.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["sha"], self.source_sha)
        self.assertIn(f"- Commit: `{self.source_sha}`", result["summary"])

    def test_confirms_direct_and_4_augenfall_from_local_artifact(self) -> None:
        """Verlangt die bewusste Direktlieferung und erlaubt den 4-Augenfall."""

        payload = {
            "tag": "r261.108",
            "sha": self.source_sha,
            "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "prepare_actor": "alice",
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
            },
        ):
            with self.assertRaisesRegex(DeliveryError, "Direktlieferung muss .* bewusst bestätigt werden"):
                run("confirm", "r261.108")
            direct = run("confirm", "r261.108", confirm_direct_delivery=True)
        with patch.dict(
            os.environ,
            {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                "GITHUB_ACTOR": "bob",
            },
        ):
            lieferung_4_augenfall = run("confirm", "r261.108")

        self.assertIn("- Lieferweg: Direktlieferung", direct["summary"])
        self.assertIn("- Lieferweg: 4-Augenfall", lieferung_4_augenfall["summary"])
        self.assertEqual(direct["outputs"]["source_sha"], self.source_sha)

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
        arguments = {"subcommand": "resolve", "tag": "r261.108"}
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "FI/mandant",
                "GITHUB_TOKEN": "secret",
                "GITHUB_API_URL": "https://github.example/api/v3",
            },
        ):
            with patch("lbs_delivery.lieferung.github.request", side_effect=(None, artifacts)):
                planned = run(**arguments)
        self.assertEqual(
            planned["outputs"],
            {
                "wiederholung": "false",
                "vorbereitung_artefakt_id": 20,
            },
        )

        reference = {"object": {"sha": self.source_sha, "type": "commit"}}
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "FI/mandant",
                "GITHUB_TOKEN": "secret",
                "GITHUB_API_URL": "https://github.example/api/v3",
            },
        ):
            with patch("lbs_delivery.lieferung.github.request", return_value=reference):
                repeated = run(**arguments)
        self.assertEqual(
            repeated["outputs"],
            {
                "wiederholung": "true",
                "source_sha": self.source_sha,
            },
        )

    def test_rejects_invalid_or_mismatched_preparation(self) -> None:
        """Lehnt beschädigte Artefakte und einen abweichenden Liefer-Tag ab."""

        preparation = self.root / "vorbereitung" / "vorbereitung.json"
        preparation.parent.mkdir()
        arguments = {"subcommand": "confirm", "tag": "r261.108"}
        with patch.dict(
            os.environ,
            {
                "GITHUB_WORKSPACE": str(self.root),
                "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                "GITHUB_ACTOR": "alice",
            },
        ):
            preparation.write_text("kein JSON", encoding="utf-8")
            with self.assertRaisesRegex(DeliveryError, "Vorbereitungsartefakt ist ungültig"):
                run(**arguments)

            preparation.write_text(
                json.dumps(
                    {
                        "tag": "r261.109",
                        "sha": self.source_sha,
                        "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
                        "prepare_actor": "alice",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(DeliveryError, "anderen Liefer-Tag"):
                run(**arguments)


if __name__ == "__main__":
    unittest.main()
