"""Prüft die Rückmeldung im GitHub Release des Mandanten-Repositories."""

from __future__ import annotations

import argparse
import json
import os
import unittest
import urllib.parse
from unittest.mock import patch

from lbs_delivery.github import run
from lbs_delivery.process import Status
from lbs_delivery.mainframe_release import _build_release

from tests.support import (
    TempDirTestCase,
    git,
    load_test_configuration,
    setup_release_repository,
)


class GitHubReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        """Bereitet die Releasehistorie und den GitHub-Kontext für den Berichtsjob vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        environment = patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(self.root),
            "GITHUB_API_URL": "https://github.example/api/v3",
            "GITHUB_REPOSITORY": self.configuration.repository,
            "GITHUB_TOKEN": "secret",
        })
        environment.start()
        self.addCleanup(environment.stop)

        self.release = {
            "id": 41,
            "html_url": "https://github.example/FI/mandant/releases/tag/r261.108",
            "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
            "assets": [],
        }

    def test_publishes_release_and_refreshes_information_file(self) -> None:
        """Prüft FULL, DELTA und das Ersetzen der Informationsdatei bei Wiederholung."""

        for tag, delivery_type, wiederholung in (
            ("r261.108", "DELTA", False),
            ("r261.100", "FULL", False),
            ("r261.108", "DELTA", True),
        ):
            with self.subTest(tag=tag, wiederholung=wiederholung):
                git(self.repository, "checkout", "--detach", tag)
                runner_temp = self.root / tag
                _build_release(self.configuration, output_directory=runner_temp / "release", tag=tag)
                information = next((runner_temp / "release").glob("_INFO_*.json"))
                content = information.read_bytes()
                source_sha = json.loads(content)["stand"]["bis"]["commit"]
                release = self.release | {"html_url": f"https://github.example/FI/mandant/releases/tag/{tag}"}
                existing = None
                if wiederholung:
                    existing = release | {"assets": [
                        {"name": information.name, "id": 51},
                        {"name": "handbuch.pdf", "id": 52},
                    ]}

                responses = [existing, release]
                if wiederholung:
                    responses.append(None)

                responses.append({"id": 61})

                with (
                    patch.dict(os.environ, {"RUNNER_TEMP": str(runner_temp)}),
                    patch("lbs_delivery.github.request", side_effect=responses) as api,
                ):
                    result = run(argparse.Namespace(tag=tag))

                calls = [call.kwargs for call in api.call_args_list]
                expected_methods = ["GET", "PATCH", "DELETE", "POST"] if wiederholung else ["GET", "POST", "POST"]
                self.assertEqual([call["method"] for call in calls], expected_methods)
                self.assertTrue(calls[0]["url"].endswith(f"/releases/tags/{tag}"))
                self.assertTrue(calls[1]["url"].endswith("/releases/41" if wiederholung else "/releases"))

                if wiederholung:
                    self.assertTrue(calls[2]["url"].endswith("/releases/assets/51"))

                body = calls[1]["payload"]["body"]
                self.assertIn(f"- Liefer-Tag: `{tag}`", body)
                self.assertIn(f"- Lieferart: `{delivery_type}`", body)
                self.assertIn(f"- Commit: `{source_sha}`", body)
                self.assertEqual(calls[-1]["content"], content)
                self.assertEqual(calls[-1]["content_type"], "application/json")
                self.assertEqual(
                    urllib.parse.parse_qs(urllib.parse.urlsplit(calls[-1]["url"]).query),
                    {"name": [information.name]},
                )
                self.assertEqual(result["status"], Status.GITHUB_RELEASE_PUBLISHED.value)
                self.assertEqual(result["release_url"], release["html_url"])


if __name__ == "__main__":
    unittest.main()
