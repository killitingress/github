"""Prüft Vorbereitung, Bestätigung und Tag der Lieferung."""

from __future__ import annotations

import argparse
import json
import os
import unittest
from unittest.mock import patch

from lbs_delivery.lieferung import _require_lieferung_source, _summary, run_aufloesen, run_command
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
        """Hält ein DELTA auf dem Bereitstellungsbranch fest und zeigt den Vorgänger."""

        git(self.repository, "switch", "-c", "bereitstellung/261.108")
        track_remote_branch(self.repository, "bereitstellung/261.108")
        releaselinie, release = _require_lieferung_source(
            self.configuration,
            self.repository,
            "r261.108",
            "bereitstellung/261.108",
            self.source_sha,
            require_current_tip=True,
        )
        summary = _summary(
            self.configuration,
            self.repository,
            "r261.108",
            "bereitstellung/261.108",
            self.source_sha,
            releaselinie,
            release,
        )
        self.assertEqual((releaselinie, release), ("261", "108"))
        self.assertIn("`DELTA`", summary)
        self.assertIn("`r261.100`", summary)
        self.assertIn("Änderungen seit `r261.107`", summary)
        self.assertIn("`D` `deleted.txt`", summary)
        self.assertIn("`A` `new.txt`", summary)

    def test_rejects_full_on_bereitstellung_and_mismatched_branch(self) -> None:
        """Lehnt .100 und einen abweichenden Bereitstellungsbranch ab."""

        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        track_remote_branch(self.repository, "bereitstellung/261.100")
        sha = git(self.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(DeliveryError, r"\.100 entsteht"):
            _require_lieferung_source(
                self.configuration,
                self.repository,
                "r261.100",
                "bereitstellung/261.100",
                sha,
                require_current_tip=True,
            )

        git(self.repository, "checkout", "release/261")
        git(self.repository, "switch", "-c", "bereitstellung/261.109")
        track_remote_branch(self.repository, "bereitstellung/261.109")
        with self.assertRaisesRegex(DeliveryError, "passt nicht zum Liefer-Tag"):
            _require_lieferung_source(
                self.configuration,
                self.repository,
                "r261.108",
                "bereitstellung/261.109",
                self.source_sha,
                require_current_tip=True,
            )

    def test_rejects_stale_tip_only_during_prepare(self) -> None:
        """Die Vorbereitung verlangt die aktuelle Branchspitze, die Ausführung nicht."""

        git(self.repository, "commit", "--allow-empty", "-m", "später")
        track_remote_branch(self.repository, "release/261")
        git(self.repository, "checkout", "--detach", self.source_sha)
        with self.assertRaisesRegex(DeliveryError, "nicht mehr aktuell"):
            _require_lieferung_source(
                self.configuration,
                self.repository,
                "r261.108",
                "release/261",
                self.source_sha,
                require_current_tip=True,
            )
        releaselinie, release = _require_lieferung_source(
            self.configuration,
            self.repository,
            "r261.108",
            "release/261",
            self.source_sha,
            require_current_tip=False,
        )
        self.assertEqual((releaselinie, release), ("261", "108"))

    def test_confirms_direct_and_four_eyes_from_local_artifact(self) -> None:
        """Verlangt die bewusste Direktlieferung und erlaubt den Vier-Augen-Weg."""

        payload = {
            "tag": "r261.108",
            "sha": self.source_sha,
            "branch": "bereitstellung/261.108",
            "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "prepare_actor": "alice",
        }
        preparation = self.root / "vorbereitung.json"
        preparation.write_text(json.dumps(payload), encoding="utf-8")

        with patch.dict(
            os.environ,
            {"SOURCE_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi"},
        ):
            with self.assertRaisesRegex(DeliveryError, "Direktlieferung muss .* bewusst bestätigt werden"):
                run_command(
                    argparse.Namespace(
                        lieferung_command="ausfuehren",
                        tag="r261.108",
                        vorbereitung=preparation,
                        actor="alice",
                        direktlieferung_bestaetigt=False,
                    )
                )
            direct = run_command(
                argparse.Namespace(
                    lieferung_command="ausfuehren",
                    tag="r261.108",
                    vorbereitung=preparation,
                    actor="alice",
                    direktlieferung_bestaetigt=True,
                )
            )
            four_eyes = run_command(
                argparse.Namespace(
                    lieferung_command="ausfuehren",
                    tag="r261.108",
                    vorbereitung=preparation,
                    actor="bob",
                    direktlieferung_bestaetigt=False,
                )
            )

        self.assertIn("Direktlieferung", direct["summary"])
        self.assertIn("Risiko bewusst bestätigt", direct["summary"])
        self.assertIn("Vier-Augen-Freigabe", four_eyes["summary"])
        self.assertEqual(direct["outputs"]["source_sha"], self.source_sha)

    def test_resolves_latest_preparation_or_existing_tag(self) -> None:
        """Verwendet den neuesten geplanten Stand und erkennt Wiederholungen."""

        artifacts = {
            "artifacts": [
                {"id": 10, "created_at": "2026-08-20T10:00:00Z", "expired": False, "workflow_run": {"id": 100}},
                {"id": 20, "created_at": "2026-08-21T10:00:00Z", "expired": False, "workflow_run": {"id": 200}},
            ]
        }
        arguments = argparse.Namespace(tag="r261.108", api_url="https://github.example/api/v3")
        with patch.dict(os.environ, {"SOURCE_REPOSITORY": "FI/mandant", "GITHUB_TOKEN": "secret"}):
            with patch("lbs_delivery.lieferung.github.request", side_effect=(None, artifacts)):
                planned = run_aufloesen(arguments)
        self.assertEqual(
            planned["outputs"],
            {
                "wiederholung": "false",
                "vorbereitung_id": 200,
                "vorbereitung_name": "r261.108-lieferungsartefakt",
            },
        )

        reference = {"object": {"sha": self.source_sha, "type": "commit"}}
        with patch.dict(os.environ, {"SOURCE_REPOSITORY": "FI/mandant", "GITHUB_TOKEN": "secret"}):
            with patch("lbs_delivery.lieferung.github.request", return_value=reference):
                repeated = run_aufloesen(arguments)
        self.assertEqual(
            repeated["outputs"],
            {
                "wiederholung": "true",
                "source_sha": self.source_sha,
            },
        )

    def test_resolves_preparations_across_all_artifact_pages(self) -> None:
        """Berücksichtigt bei häufigen Vorbereitungen alle Artefaktseiten."""

        first_page = {
            "artifacts": [
                {
                    "id": artifact_id,
                    "created_at": "2026-08-20T10:00:00Z",
                    "expired": False,
                    "workflow_run": {"id": artifact_id},
                }
                for artifact_id in range(1, 101)
            ]
        }
        second_page = {
            "artifacts": [
                {
                    "id": 101,
                    "created_at": "2026-08-21T10:00:00Z",
                    "expired": False,
                    "workflow_run": {"id": 501},
                }
            ]
        }
        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            """Liefert Tag-Prüfung und zwei aufeinanderfolgende Artefaktseiten."""

            calls.append(arguments)
            return (None, first_page, second_page)[len(calls) - 1]

        with patch.dict(os.environ, {"SOURCE_REPOSITORY": "FI/mandant", "GITHUB_TOKEN": "secret"}):
            with patch("lbs_delivery.lieferung.github.request", side_effect=request):
                result = run_aufloesen(
                    argparse.Namespace(tag="r261.108", api_url="https://github.example/api/v3")
                )

        self.assertEqual(result["outputs"]["vorbereitung_id"], 501)
        self.assertIn("page=1", calls[1]["url"])
        self.assertIn("page=2", calls[2]["url"])

    def test_rejects_invalid_or_mismatched_preparation(self) -> None:
        """Lehnt beschädigte Artefakte und einen abweichenden Liefer-Tag ab."""

        preparation = self.root / "vorbereitung.json"
        arguments = argparse.Namespace(
            lieferung_command="ausfuehren",
            tag="r261.108",
            vorbereitung=preparation,
            actor="alice",
            direktlieferung_bestaetigt=False,
        )
        with patch.dict(os.environ, {"SOURCE_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi"}):
            preparation.write_text("kein JSON", encoding="utf-8")
            with self.assertRaisesRegex(DeliveryError, "Vorbereitungsartefakt ist ungültig"):
                run_command(arguments)

            preparation.write_text(
                json.dumps(
                    {
                        "tag": "r261.109",
                        "sha": self.source_sha,
                        "branch": "release/261",
                        "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
                        "prepare_actor": "alice",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(DeliveryError, "anderen Liefer-Tag"):
                run_command(arguments)

    def test_creates_tag(self) -> None:
        """Erzeugt den Liefer-Tag über die GitHub-API."""

        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            """Zeichnet den GitHub-Aufruf zur Tag-Erstellung auf."""

            calls.append(arguments)
            return {"ref": "refs/tags/r261.108"}

        with patch("lbs_delivery.lieferung.github.request", side_effect=request):
            with patch.dict(
                os.environ,
                {
                    "GITHUB_WORKSPACE": str(self.root),
                    "SOURCE_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
                    "WORKFLOW_CONFIGURATION_TOKEN": "secret",
                },
            ):
                run_command(
                    argparse.Namespace(
                        lieferung_command="tag",
                        tag="r261.108",
                        branch="release/261",
                        source_sha=self.source_sha,
                        api_url="https://github.example/api/v3",
                    )
                )
        self.assertEqual(calls[-1]["payload"], {"ref": "refs/tags/r261.108", "sha": self.source_sha})


if __name__ == "__main__":
    unittest.main()
