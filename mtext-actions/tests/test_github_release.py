"""Prüft die Rückmeldung im GitHub Release des Mandanten-Repositories."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from lbs_delivery.github import _publish_release
from lbs_delivery.process import Status
from lbs_delivery.mainframe_release import _build_release

from tests.support import (
    TempDirTestCase,
    git,
    jcl_template,
    load_test_configuration,
    setup_release_repository,
)


class GitHubReleaseTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)
        self.dist = self.root / "dist"

        git(self.repository, "checkout", "--detach", "r261.108")
        _build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.dist,
            jcl_template=jcl_template(),
            tag="r261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )

    def test_creates_release_and_uploads_information_file(self) -> None:
        """Prüft Anlage, Beschreibung und Informationsdatei des Releases."""

        calls: list[dict[str, object]] = []

        def request(**arguments: object) -> object:
            """Zeichnet den GitHub-Aufruf auf und liefert die passende Testantwort."""

            calls.append(arguments)
            if arguments["method"] == "GET":
                return None

            if arguments.get("payload") is not None:
                return {
                    "id": 41,
                    "html_url": "https://github.example/FI/mandant/releases/tag/r261.108",
                    "upload_url": "https://uploads.github.example/repos/FI/mandant/releases/41/assets{?name,label}",
                    "assets": [],
                }
            return {"id": 51}

        # Veröffentlichung und GitHub-Antworten gemeinsam im geprüften Ablauf halten.
        with patch("lbs_delivery.github.request", side_effect=request):
            result = _publish_release(
                artifact_root=self.dist,
                api_url="https://github.example/api/v3",
                server_url="https://github.example",
                repository=self.configuration.repository,
                liefer_tag="r261.108",
                source_sha="1" * 40,
                token="secret",
            )

        self.assertEqual(result["status"], Status.GITHUB_RELEASE_PUBLISHED.value)
        self.assertEqual(result["liefer_tag"], "r261.108")
        body = next(call for call in calls if call.get("payload") is not None)["payload"]["body"]
        self.assertIn("## Lieferung", body)
        self.assertIn("- Liefer-Tag: `r261.108`", body)
        self.assertIn("LOMS_Basis", body)
        self.assertIn("releases/download/r261.108/_INFO_FI-LOMS_Basis.json", body)
        uploads = [call for call in calls if call.get("content") is not None]
        self.assertEqual(len(uploads), 1)
        self.assertIn("_INFO_FI-LOMS_Basis.json", uploads[0]["url"])
        self.assertEqual(uploads[0]["content_type"], "application/json")


if __name__ == "__main__":
    unittest.main()
