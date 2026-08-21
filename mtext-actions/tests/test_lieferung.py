"""Prüft Vorbereitung, Bestätigung und Tag der Lieferung."""

from __future__ import annotations

import argparse
import json
import os
import unittest
from unittest.mock import patch

from lbs_delivery.lieferung import _require_lieferung_source, _summary, run_command
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
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "123456"}):
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
        self.assertIn("| Vorbereitungs-ID | `123456` |", summary)
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

        git(self.repository, "tag", "r261.108", self.source_sha)
        with self.assertRaisesRegex(DeliveryError, "bereits vorhanden"):
            _require_lieferung_source(
                self.configuration,
                self.repository,
                "r261.108",
                "release/261",
                self.source_sha,
                require_current_tip=False,
            )

    def test_confirms_direct_and_four_eyes_from_local_artifact(self) -> None:
        """Leitet den Lieferweg aus vorbereitender und ausführender Person ab."""

        payload = {
            "tag": "r261.108",
            "sha": self.source_sha,
            "branch": "bereitstellung/261.108",
            "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "actor": "alice",
        }
        preparation = self.root / "vorbereitung.json"
        preparation.write_text(json.dumps(payload), encoding="utf-8")

        with patch.dict(
            os.environ,
            {"SOURCE_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi"},
        ):
            direct = run_command(
                argparse.Namespace(
                    lieferung_command="ausfuehren",
                    vorbereitung=preparation,
                    actor="alice",
                )
            )
            four_eyes = run_command(
                argparse.Namespace(
                    lieferung_command="ausfuehren",
                    vorbereitung=preparation,
                    actor="bob",
                )
            )

        self.assertIn("Direktlieferung", direct["summary"])
        self.assertIn("Vier-Augen-Freigabe", four_eyes["summary"])
        self.assertEqual(direct["outputs"]["source_sha"], self.source_sha)

        preparation.write_text("kein JSON", encoding="utf-8")
        with patch.dict(os.environ, {"SOURCE_REPOSITORY": payload["repository"]}):
            with self.assertRaisesRegex(DeliveryError, "Vorbereitungsartefakt ist ungültig"):
                run_command(
                    argparse.Namespace(
                        lieferung_command="ausfuehren",
                        vorbereitung=preparation,
                        actor="alice",
                    )
                )

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
                        prepare_actor="alice",
                        execute_actor="bob",
                        api_url="https://github.example/api/v3",
                    )
                )
        self.assertEqual(calls[-1]["payload"], {"ref": "refs/tags/r261.108", "sha": self.source_sha})


if __name__ == "__main__":
    unittest.main()
