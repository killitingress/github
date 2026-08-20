"""Prüft die Rückmeldung im GitHub Release des Mandanten-Repositories."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from lbs_delivery.github import publish_release
from lbs_delivery.process import Status
from lbs_delivery.mainframe_release import build_release

from tests.support import (
    TempDirTestCase,
    git,
    jcl_template,
    load_test_configuration,
    setup_release_repository,
)

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
        self.configuration = load_test_configuration(
            self.repository,
            mandant={"letztes_release": "v261.108"},
        )
        self.dist = self.root / "dist"

        git(self.repository, "checkout", "--detach", "v261.108")
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

        with patch("lbs_delivery.github.request", side_effect=request):
            result = publish_release(
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
        self.assertIn("releases/download/v261.108/_INFO_FI-LOMS_Basis.json", body)
        uploads = [call for call in calls if call.get("content") is not None]
        self.assertEqual(len(uploads), 1)
        self.assertIn("_INFO_FI-LOMS_Basis.json", uploads[0]["url"])
        self.assertEqual(uploads[0]["content_type"], "application/json")


if __name__ == "__main__":
    unittest.main()
