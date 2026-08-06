"""Prüft die Rückmeldung im GitHub Release des Mandanten-Repositories."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.github_release import publish_github_release
from lbs_delivery.process import Status
from lbs_delivery.release import build_release

from tests.support import git, load_test_configuration, setup_release_repository


class GitHubReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt eine vollständige DELTA-Lieferung für die GitHub-API-Tests."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.dist = self.root / "dist"
        self.manifest = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.dist,
            tag="v261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )

    def test_creates_release_with_summary_and_information_file(self) -> None:
        """Prüft Neuanlage, lesbare Zusammenfassung und den einzelnen Download."""

        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            """Bildet die erwarteten GitHub-Antworten ohne Netzwerkzugriff nach."""

            calls.append(arguments)
            if arguments["method"] == "GET":
                return None
            if arguments.get("payload") is not None:
                return {
                    "id": 41,
                    "html_url": "https://github.example/FI/mandant/releases/tag/v261.108",
                    "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
                    "assets": [],
                }
            return {"id": 51}

        with patch("lbs_delivery.github_release._github_request", side_effect=request):
            result = publish_github_release(
                manifest_path=self.manifest,
                artifact_root=self.dist,
                api_url="https://github.example/api/v3",
                server_url="https://github.example",
                repository=self.configuration.repository,
                release_tag="v261.108",
                token="secret",
            )

        self.assertEqual(result["status"], Status.GITHUB_RELEASE_PUBLISHED.value)
        create = next(call for call in calls if call.get("payload") is not None)
        body = create["payload"]["body"]
        self.assertIn("## Lieferung", body)
        self.assertIn("LOMS_Basis", body)
        self.assertIn("| 4 |", body)
        self.assertIn("releases/download/v261.108/_INFO_FI-LOMS_Basis-DELTA", body)
        uploads = [call for call in calls if call.get("content") is not None]
        self.assertEqual(len(uploads), 1)
        self.assertIn("_INFO_FI-LOMS_Basis-DELTA", uploads[0]["url"])

    def test_updates_existing_release_and_replaces_own_asset(self) -> None:
        """Prüft die wiederholbare Aktualisierung eines vorhandenen Releases."""

        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            """Liefert ein vorhandenes Release und zeichnet dessen Aktualisierung auf."""

            calls.append(arguments)
            if arguments["method"] == "GET":
                return {
                    "id": 41,
                    "html_url": "https://github.example/FI/mandant/releases/tag/v261.108",
                    "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
                    "assets": [
                        {
                            "id": 52,
                            "name": "_INFO_FI-LOMS_Basis-DELTA-v261.108-v261.107.txt",
                        },
                        {"id": 53, "name": "fremde-datei.txt"},
                    ],
                }
            if arguments["method"] == "PATCH":
                return {
                    "id": 41,
                    "html_url": "https://github.example/FI/mandant/releases/tag/v261.108",
                    "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
                }
            return None

        with patch("lbs_delivery.github_release._github_request", side_effect=request):
            publish_github_release(
                manifest_path=self.manifest,
                artifact_root=self.dist,
                api_url="https://github.example/api/v3",
                server_url="https://github.example",
                repository=self.configuration.repository,
                release_tag="v261.108",
                token="secret",
            )

        methods = [call["method"] for call in calls]
        self.assertEqual(methods, ["GET", "PATCH", "DELETE", "POST"])
        self.assertTrue(calls[2]["url"].endswith("/releases/assets/52"))
        self.assertNotIn("53", " ".join(str(call["url"]) for call in calls))


if __name__ == "__main__":
    unittest.main()
