"""Prüft die Rückmeldung im GitHub Release des Mandanten-Repositories."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from lbs_delivery.github_release import publish_github_release
from lbs_delivery.process import Status
from lbs_delivery.mainframe_release import build_release

from tests.support import TempDirTestCase, git, jcl_template, load_test_configuration, setup_release_repository

PUBLISH_KWARGS = {
    "api_url": "https://github.example/api/v3",
    "server_url": "https://github.example",
    "release_tag": "v261.108",
    "source_sha": "1" * 40,
    "token": "secret",
}


class GitHubReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.dist = self.root / "dist"
        build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.dist,
            jcl_template=jcl_template(),
            tag="v261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )

    def publish(self, handler) -> tuple[list[dict[str, object]], dict[str, object]]:
        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            calls.append(arguments)
            return handler(arguments)

        with patch("lbs_delivery.github_release._github_request", side_effect=request):
            result = publish_github_release(
                artifact_root=self.dist,
                repository=self.configuration.repository,
                **PUBLISH_KWARGS,
            )
        return calls, result

    def test_creates_release_and_uploads_information_file(self) -> None:
        def handler(arguments: dict[str, object]) -> object:
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

        calls, result = self.publish(handler)
        self.assertEqual(result["status"], Status.GITHUB_RELEASE_PUBLISHED.value)
        body = next(call for call in calls if call.get("payload") is not None)["payload"]["body"]
        self.assertIn("## Lieferung", body)
        self.assertIn("LOMS_Basis", body)
        self.assertIn("releases/download/v261.108/_INFO_FI-LOMS_Basis-DELTA", body)
        uploads = [call for call in calls if call.get("content") is not None]
        self.assertEqual(len(uploads), 1)
        self.assertIn("_INFO_FI-LOMS_Basis-DELTA", uploads[0]["url"])

    def test_updates_existing_release_without_touching_foreign_assets(self) -> None:
        def handler(arguments: dict[str, object]) -> object:
            if arguments["method"] == "GET":
                return {
                    "id": 41,
                    "html_url": "https://github.example/FI/mandant/releases/tag/v261.108",
                    "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
                    "assets": [
                        {"id": 52, "name": "_INFO_FI-LOMS_Basis-DELTA-v261.108-v261.107.txt"},
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

        calls, _result = self.publish(handler)
        self.assertEqual([call["method"] for call in calls], ["GET", "PATCH", "DELETE", "POST"])
        self.assertTrue(calls[2]["url"].endswith("/releases/assets/52"))
        self.assertNotIn("53", " ".join(str(call["url"]) for call in calls))


if __name__ == "__main__":
    unittest.main()
