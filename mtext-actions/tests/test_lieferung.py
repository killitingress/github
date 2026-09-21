"""Prüft Vorbereitung und Bestätigung der Lieferung."""

from __future__ import annotations

import hashlib
import os
import unittest
from unittest.mock import patch

from lbs_delivery import github
from lbs_delivery.git import LieferTag
from lbs_delivery.lieferung import liefer_tag_for_branch, run
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.project_packages import lieferumfang, previous_release_scope, project_elements

from tests.support import TempDirTestCase, git, load_test_configuration, setup_release_repository, track_remote_branch


class LieferungTests(TempDirTestCase):
    """Prüft Liefer-Tag, Branchzuordnung, Lieferumfang und Bestätigung."""

    def setUp(self) -> None:
        """Bereitet einen noch nicht getaggten DELTA-Commit vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        git(self.repository, "tag", "-d", "r261.108")
        self.configuration = load_test_configuration(self.repository)
        self.source_sha = git(self.repository, "rev-parse", "HEAD")

    def test_liefer_tag_branch_and_scopes(self) -> None:
        """Prüft Liefer-Tag, Branchzuordnung und getrennte DELTA-Umfänge."""

        tag = LieferTag.parse("r261.108")
        self.assertEqual(tag.releaselinie, "261")
        self.assertEqual(tag.zwischenrelease, "108")
        self.assertFalse(tag.ist_hauptrelease)
        self.assertLess(tag, LieferTag.parse("r270.100"))
        self.assertEqual(tag, LieferTag.from_bereitstellung("bereitstellung/261.108"))
        self.assertTrue(LieferTag.parse("r261.100").ist_hauptrelease)
        self.assertIsNone(LieferTag.from_bereitstellung("anderer-branch"))
        with self.assertRaises(ValueError):
            LieferTag.parse("r261.099")

        self.assertEqual(str(liefer_tag_for_branch(self.configuration, "main")), "r270.100")
        self.assertEqual(str(liefer_tag_for_branch(self.configuration, "release/261")), "r261.100")
        self.assertEqual(
            str(liefer_tag_for_branch(self.configuration, "bereitstellung/261.108")),
            "r261.108",
        )

        previous_scope = previous_release_scope(self.repository, tag, self.source_sha)
        scope = lieferumfang(self.repository, tag, self.source_sha)
        information_elements = project_elements(self.repository, "LOMS_Basis", previous_scope)
        package_elements = project_elements(self.repository, "LOMS_Basis", scope)
        self.assertIn(["D", "transient.txt"], information_elements)
        self.assertNotIn(["M", "baseline.txt"], information_elements)
        self.assertNotIn(["D", "transient.txt"], package_elements)
        self.assertIn(["M", "baseline.txt"], package_elements)

        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_for_branch(self.configuration, "bereitstellung/261.100")
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_for_branch(self.configuration, "feature/261/beispiel")
        self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

    def test_prepares_checkout_after_branch_advances(self) -> None:
        """Die Vorbereitung hält den Lauf-Commit bei weiterentwickeltem Branch fest."""

        git(self.repository, "tag", "-d", "r261.100")
        git(self.repository, "commit", "--allow-empty", "-m", "später")
        track_remote_branch(self.repository, "release/261")
        git(self.repository, "checkout", "--detach", self.source_sha)
        load_test_configuration(self.repository, mandant={"dry_run": True})

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
                    {"name": "lieferung:vorbereitet"},
                    None,
                    {"name": "dry_run"},
                    {
                        "number": 42,
                        "labels": [{"name": "lieferung:vorbereitet"}, {"name": "dry_run"}],
                    },
                ),
            ) as api:
                result = run("check")

        body = api.call_args.kwargs["payload"]["body"]
        self.assertNotIn("outputs", result)
        # Der später gestartete Lauf übernimmt den im Issue festgehaltenen Commit.
        with patch.dict(os.environ, {
            "GITHUB_ACTOR": "alice",
            "GITHUB_SERVER_URL": "https://github.example",
            "GITHUB_REPOSITORY": "FinanzInformatik/fi_lbs_entw_oms_fi",
            "GITHUB_RUN_ID": "5678",
        }        ), patch("lbs_delivery.lieferung.github.repository_role", return_value="maintain"), patch(
            "lbs_delivery.lieferung.github.issue",
            return_value=("open", {"lieferung:vorbereitet"}, "Lieferung r261.100", body),
        ), patch("lbs_delivery.lieferung.github.replace_issue_label") as mark_started, patch(
            "lbs_delivery.lieferung.github.comment_issue",
        ) as comment:
            confirmed = run("resolve", issue=42)
        self.assertEqual(confirmed["status"], Status.LIEFERSTAND_ERMITTELT)
        self.assertEqual(confirmed["outputs"]["source_sha"], self.source_sha)
        self.assertEqual(confirmed["outputs"]["liefer_tag"], "r261.100")
        mark_started.assert_called_once()
        comment.assert_called_once()

    def test_freigabe_lifecycle(self) -> None:
        """Prüft Abschluss, Tag und den GitHub-Issue-Pfad."""

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
                "RUNNER_TEMP": str(self.root / "runner-temp"),
            },
        ):
            with patch("lbs_delivery.lieferung.github._request") as api:
                incomplete = run("incomplete", issue=42)
            self.assertEqual(incomplete["status"], Status.LIEFERUNG_NICHT_ABGESCHLOSSEN)
            api.assert_called_once()

            with patch("lbs_delivery.lieferung.github._request", return_value={"role_name": "write"}):
                with self.assertRaises(DeliveryError) as raised:
                    run("resolve", issue=42)
            self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

            archives = self.root / "runner-temp" / "release"
            archives.mkdir(parents=True)
            (archives / "FIBASISD.tgz").write_bytes(b"lieferdatei")
            (archives / "FIBASISF.tgz").write_bytes(b"vollstand")
            (archives / "FIBASISD.jcl").write_bytes(b"//JCL\n")
            with patch("lbs_delivery.lieferung.github._request", side_effect=(
                {},
                {"name": "lieferung:abgeschlossen"},
                {"state": "open", "title": "Lieferung r261.108",
                 "labels": [{"name": "lieferung:gestartet"}]},
                [{"name": "lieferung:abgeschlossen"}],
                {},
            )) as api:
                completed = run("complete", "r261.108", issue=42)
            self.assertEqual(completed["status"], Status.LIEFERUNG_ABGESCHLOSSEN)
            self.assertEqual([e.kwargs["method"] for e in api.call_args_list], ["POST", "GET", "GET", "PUT", "PATCH"])
            completion_body = api.call_args_list[0].kwargs["payload"]["body"]
            self.assertIn(f"| `FIBASISD.tgz` | `{hashlib.sha256(b'lieferdatei').hexdigest()}` |", completion_body)
            self.assertNotIn("FIBASISD.jcl", completion_body)

            with patch("lbs_delivery.github._request", side_effect=(
                {},
                {"name": "lieferung:abgeschlossen"},
                {"state": "closed", "title": "Lieferung r261.108",
                 "labels": [{"name": "lieferung:abgeschlossen"}, {"name": "dry_run"}]},
                {},
            )) as api:
                github.complete_issue(
                    42, "Wiederholung abgeschlossen", "lieferung:gestartet",
                    "lieferung:abgeschlossen", "Lieferlauf wurde abgeschlossen",
                )
            self.assertEqual([e.kwargs["method"] for e in api.call_args_list], ["POST", "GET", "GET", "PATCH"])

            with patch("lbs_delivery.github._request", side_effect=({"sha": "tag-object"}, {})) as api:
                github.create_tag("r261.108", self.source_sha, 42)
            self.assertEqual(api.call_args_list[0].kwargs["payload"]["message"], "Freigabe-Issue: #42")

            with patch("lbs_delivery.github._request", side_effect=(
                {"name": "lieferung:gestartet"},
                {"state": "open", "title": "Lieferung r261.108",
                 "labels": [{"name": "lieferung:vorbereitet"}, {"name": "dry_run"}]},
                [{"name": "lieferung:gestartet"}, {"name": "dry_run"}],
            )) as api:
                github.replace_issue_label(42, "lieferung:vorbereitet", "lieferung:gestartet", "Gestartet")
            self.assertEqual(api.call_args_list[2].kwargs["payload"]["labels"], ["dry_run", "lieferung:gestartet"])

            with patch("lbs_delivery.github._request", side_effect=(
                {"object": {"sha": "tag-object", "type": "tag"}},
                {"tag": "r261.108", "message": str(42),
                 "object": {"type": "commit", "sha": self.source_sha}},
            )):
                with self.assertRaises(DeliveryError) as raised:
                    github.tag_record("r261.108")
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

            with patch.dict(os.environ, {"SOURCE_SHA": self.source_sha}):
                with (
                    patch("lbs_delivery.lieferung.github.tag_record", return_value=None),
                    patch("lbs_delivery.lieferung.github.create_tag") as create_tag,
                ):
                    result = run("tag", "r261.108", issue=42)
                self.assertEqual(result["status"], Status.LIEFERUNG_TAGGED)
                create_tag.assert_called_once_with("r261.108", self.source_sha, 42)

                with (
                    patch("lbs_delivery.lieferung.github.tag_record", return_value=(self.source_sha, 42)),
                    patch("lbs_delivery.lieferung.github.create_tag") as create_tag,
                ):
                    run("tag", "r261.108", issue=42)
                create_tag.assert_not_called()

                for record in (("anderer-commit", 42), (self.source_sha, 41)):
                    with patch("lbs_delivery.lieferung.github.tag_record", return_value=record):
                        with self.assertRaises(DeliveryError) as raised:
                            run("tag", "r261.108", issue=42)
                    self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

    def test_resolve_repetition(self) -> None:
        """Ermittelt Wiederholungen und lehnt ungültige Aufrufe ab."""

        env = {
            "GITHUB_REPOSITORY": "FI/mandant",
            "GITHUB_ACTOR": "alice",
            "GITHUB_TOKEN": "secret",
            "GITHUB_API_URL": "https://github.example/api/v3",
            "GITHUB_SERVER_URL": "https://github.example",
        }
        reference = {"object": {"sha": "tag-object", "type": "tag"}}
        annotation = {"tag": "r261.108", "message": "Freigabe-Issue: #42",
                      "object": {"type": "commit", "sha": self.source_sha}}
        with patch.dict(os.environ, env), patch(
            "lbs_delivery.lieferung.github._request",
            side_effect=(
                {"role_name": "admin"},
                {"state": "closed", "title": "Lieferung r261.108",
                 "labels": [{"name": "lieferung:abgeschlossen"}]},
                reference, annotation,
            ),
        ):
            repeated = run("resolve", issue=42)
        self.assertEqual(repeated["status"], Status.LIEFERSTAND_ERMITTELT)
        self.assertEqual(
            repeated["outputs"],
            {"wiederholung": "true", "source_sha": self.source_sha, "liefer_tag": "r261.108"},
        )

        with self.assertRaises(DeliveryError) as raised:
            run("resolve", issue=0)
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        with patch.dict(os.environ, env), patch(
            "lbs_delivery.lieferung.github._request",
            side_effect=(
                {"role_name": "admin"},
                {"state": "closed", "title": "Lieferung r261.108",
                 "labels": [{"name": "lieferung:gestartet"}]},
                {"object": {"type": "commit", "sha": self.source_sha}},
            ),
        ):
            with self.assertRaises(DeliveryError) as raised:
                run("resolve", issue=42)
        self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

        with patch.dict(os.environ, {"GITHUB_ACTOR": "alice"}), patch(
            "lbs_delivery.lieferung.github.repository_role", return_value="maintain"
        ), patch("lbs_delivery.lieferung.github.issue") as issue_mock, patch(
            "lbs_delivery.lieferung.github.tag_record"
        ) as tag_record:
            issue_mock.return_value = ("closed", {"lieferung:gestartet"}, "Kein Liefer-Tag", "")
            with self.assertRaises(DeliveryError) as raised:
                run("resolve", issue=42)
            self.assertEqual(raised.exception.status, Status.FREIGABE_FAILED)
            tag_record.assert_not_called()

            issue_mock.return_value = ("closed", {"lieferung:gestartet"}, "Lieferung r261.108", "")
            tag_record.return_value = (self.source_sha, 41)
            with self.assertRaises(DeliveryError) as raised:
                run("resolve", issue=42)
            self.assertEqual(raised.exception.status, Status.FREIGABE_FAILED)

    def test_invalid_issue_body_does_not_start_delivery(self) -> None:
        """Ein Issue ohne festgehaltenen Lieferstand startet keine Lieferung."""

        with (
            patch.dict(os.environ, {"GITHUB_ACTOR": "alice"}),
            patch("lbs_delivery.lieferung.github.repository_role", return_value="maintain"),
            patch("lbs_delivery.lieferung.github.issue", return_value=(
                "open", {"lieferung:vorbereitet"}, "Lieferung r261.108", "",
            )),
            patch("lbs_delivery.lieferung.github.replace_issue_label") as mark_started,
        ):
            with self.assertRaises(DeliveryError) as raised:
                run("resolve", issue=42)
        self.assertEqual(raised.exception.status, Status.FREIGABE_FAILED)
        mark_started.assert_not_called()


if __name__ == "__main__":
    unittest.main()
