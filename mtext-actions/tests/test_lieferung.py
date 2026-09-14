"""Prüft Vorbereitung und Bestätigung der Lieferung."""

from __future__ import annotations

import json
import hashlib
import os
import unittest
from unittest.mock import patch

from lbs_delivery import github
from lbs_delivery.git import LieferTag
from lbs_delivery.lieferung import liefer_tag_fuer_branch, run
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.project_packages import previous_release_scope, project_elements, release_scope

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

        self.assertEqual(str(liefer_tag_fuer_branch(self.configuration, "main")), "r270.100")
        self.assertEqual(str(liefer_tag_fuer_branch(self.configuration, "release/261")), "r261.100")
        self.assertEqual(
            str(liefer_tag_fuer_branch(self.configuration, "bereitstellung/261.108")),
            "r261.108",
        )

        vorrelease_scope = previous_release_scope(self.repository, tag, self.source_sha)
        paket_scope = release_scope(self.repository, tag, self.source_sha)
        information_elements = project_elements(self.repository, "LOMS_Basis", vorrelease_scope)
        paket_elements = project_elements(self.repository, "LOMS_Basis", paket_scope)
        self.assertIn(["D", "transient.txt"], information_elements)
        self.assertNotIn(["M", "baseline.txt"], information_elements)
        self.assertNotIn(["D", "transient.txt"], paket_elements)
        self.assertIn(["M", "baseline.txt"], paket_elements)

        git(self.repository, "checkout", "--detach", "r261.100")
        git(self.repository, "switch", "-c", "bereitstellung/261.100")
        git(self.repository, "tag", "-d", "r261.100")
        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_fuer_branch(self.configuration, "bereitstellung/261.100")
        self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        with self.assertRaises(DeliveryError) as raised:
            liefer_tag_fuer_branch(self.configuration, "feature/261/beispiel")
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
                    {"name": "lieferung:freigabe"},
                    None,
                    {"name": "dry_run"},
                    {
                        "number": 42,
                        "labels": [{"name": "lieferung:freigabe"}, {"name": "dry_run"}],
                    },
                ),
            ) as api:
                result = run("check")

        payload = json.loads((self.root / "vorbereitung.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["sha"], self.source_sha)
        self.assertEqual(payload["tag"], "r261.100")
        self.assertEqual(payload["issue"], 42)
        self.assertEqual(result["outputs"]["vorbereitung_name"], "lieferung-42-vorbereitungsartefakt")
        self.assertEqual(api.call_args.kwargs["payload"]["labels"], ["lieferung:freigabe", "dry_run"])

    def test_freigabe_lifecycle(self) -> None:
        """Prüft Freigabe, Bestätigung, Abschluss, Tag und den GitHub-Issue-Pfad."""

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
                "RUNNER_TEMP": str(self.root / "runner-temp"),
            },
        ):
            issue = {"state": "open", "title": "Lieferung r261.108 freigeben",
                     "labels": [{"name": "lieferung:freigabe"}]}
            artifacts = {"artifacts": [{"id": 20, "created_at": "2026-08-21T10:00:00Z", "expired": False}]}

            with patch(
                "lbs_delivery.lieferung.github._request",
                side_effect=({"role_name": "maintain"}, issue, artifacts),
            ):
                result = run("resolve", issue=42)
            self.assertEqual(result["status"], Status.LIEFERSTAND_ERMITTELT)

            with (
                patch("lbs_delivery.lieferung.github.replace_issue_label") as mark_started,
                patch("lbs_delivery.lieferung.github._request") as api,
            ):
                confirmed = run("confirm", issue=42)
            self.assertEqual(confirmed["status"], Status.LIEFERUNG_BESTAETIGT)
            self.assertEqual(confirmed["outputs"], {"source_sha": self.source_sha, "liefer_tag": "r261.108"})
            mark_started.assert_called_once()

            with patch("lbs_delivery.lieferung.github._request") as api:
                incomplete = run("incomplete", issue=42)
            self.assertEqual(incomplete["status"], Status.LIEFERUNG_NICHT_ABGESCHLOSSEN)
            api.assert_called_once()

            with patch("lbs_delivery.lieferung.github._request", return_value={"role_name": "write"}):
                with self.assertRaises(DeliveryError) as raised:
                    run("resolve", issue=42)
            self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

            with self.assertRaises(DeliveryError) as raised:
                run("confirm", issue=41)
            self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

            archives = self.root / "runner-temp" / "release"
            archives.mkdir(parents=True)
            (archives / "FIBASISD.tgz").write_bytes(b"lieferdatei")
            (archives / "FIBASISF.tgz").write_bytes(b"vollstand")
            (archives / "FIBASISD.jcl").write_bytes(b"//JCL\n")
            with patch("lbs_delivery.lieferung.github._request", side_effect=(
                {},
                {"name": "lieferung:abgeschlossen"},
                {"state": "open", "title": "Lieferung r261.108 freigeben",
                 "labels": [{"name": "lieferung:gestartet"}]},
                [{"name": "lieferung:abgeschlossen"}],
                {},
            )) as api:
                completed = run("complete", "r261.108", issue=42)
            self.assertEqual(completed["status"], Status.LIEFERUNG_ABGESCHLOSSEN)
            self.assertEqual([e.kwargs["method"] for e in api.call_args_list], ["POST", "GET", "GET", "PUT", "PATCH"])
            body = api.call_args_list[0].kwargs["payload"]["body"]
            self.assertIn(f"| `FIBASISD.tgz` | `{hashlib.sha256(b'lieferdatei').hexdigest()}` |", body)
            self.assertNotIn("FIBASISD.jcl", body)

            with patch("lbs_delivery.github._request", side_effect=(
                {},
                {"name": "lieferung:abgeschlossen"},
                {"state": "closed", "title": "Lieferung r261.108 freigeben",
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
                {"state": "open", "title": "Lieferung r261.108 freigeben",
                 "labels": [{"name": "lieferung:freigabe"}, {"name": "dry_run"}]},
                [{"name": "lieferung:gestartet"}, {"name": "dry_run"}],
            )) as api:
                github.replace_issue_label(42, "lieferung:freigabe", "lieferung:gestartet", "Gestartet")
            self.assertEqual(api.call_args_list[2].kwargs["payload"]["labels"], ["dry_run", "lieferung:gestartet"])

            with patch("lbs_delivery.github._request", side_effect=(
                {"object": {"sha": "tag-object", "type": "tag"}},
                {"tag": "r261.108", "message": "Freigabe-Issue: #0",
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

    def test_resolve_and_repeat(self) -> None:
        """Ermittelt Vorbereitung oder Wiederholung und lehnt ungültige Fälle ab."""

        artifacts = {
            "artifacts": [
                {"id": 10, "created_at": "2026-08-20T10:00:00Z", "expired": False, "workflow_run": {"id": 100}},
                {"id": 20, "created_at": "2026-08-21T10:00:00Z", "expired": False, "workflow_run": {"id": 200}},
                {"id": 30, "created_at": "2026-08-22T10:00:00Z", "expired": True, "workflow_run": {"id": 300}},
            ]
        }
        env = {
            "GITHUB_REPOSITORY": "FI/mandant",
            "GITHUB_ACTOR": "alice",
            "GITHUB_TOKEN": "secret",
            "GITHUB_API_URL": "https://github.example/api/v3",
        }
        issue = {"state": "open", "title": "Lieferung r261.108 freigeben",
                 "labels": [{"name": "lieferung:freigabe"}]}
        with patch.dict(os.environ, env), patch(
            "lbs_delivery.lieferung.github._request",
            side_effect=({"role_name": "maintain"}, issue, artifacts),
        ):
            planned = run("resolve", issue=42)
        self.assertEqual(planned["outputs"], {"wiederholung": "false", "vorbereitung_artefakt_id": 20})

        reference = {"object": {"sha": "tag-object", "type": "tag"}}
        annotation = {"tag": "r261.108", "message": "Freigabe-Issue: #42",
                      "object": {"type": "commit", "sha": self.source_sha}}
        with patch.dict(os.environ, env), patch(
            "lbs_delivery.lieferung.github._request",
            side_effect=(
                {"role_name": "admin"},
                {"state": "closed", "title": "Lieferung r261.108 freigeben",
                 "labels": [{"name": "lieferung:abgeschlossen"}]},
                reference, annotation,
            ),
        ):
            repeated = run("repeat", issue=42)
        self.assertEqual(
            repeated["outputs"],
            {"wiederholung": "true", "source_sha": self.source_sha, "liefer_tag": "r261.108"},
        )

        for invalid in ({"issue": 0}, {"tag": "r261.108", "issue": 42}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(DeliveryError) as raised:
                    run("resolve", **invalid)
                self.assertEqual(raised.exception.status, Status.VALIDATION_FAILED)

        with patch.dict(os.environ, env), patch(
            "lbs_delivery.lieferung.github._request",
            side_effect=(
                {"role_name": "admin"},
                {"state": "closed", "title": "Lieferung r261.108 freigeben",
                 "labels": [{"name": "lieferung:gestartet"}]},
                {"object": {"type": "commit", "sha": self.source_sha}},
            ),
        ):
            with self.assertRaises(DeliveryError) as raised:
                run("repeat", issue=42)
        self.assertEqual(raised.exception.status, Status.SOURCE_FAILED)

        with patch.dict(os.environ, {"GITHUB_ACTOR": "alice"}), patch(
            "lbs_delivery.lieferung.github.repository_role", return_value="maintain"
        ), patch("lbs_delivery.lieferung.github.issue") as issue_mock, patch(
            "lbs_delivery.lieferung.github.tag_record"
        ) as tag_record:
            issue_mock.return_value = ("closed", {"lieferung:gestartet"}, "Kein Liefer-Tag")
            with self.assertRaises(DeliveryError) as raised:
                run("repeat", issue=42)
            self.assertEqual(raised.exception.status, Status.FREIGABE_FAILED)
            tag_record.assert_not_called()

            issue_mock.return_value = ("closed", {"lieferung:gestartet"}, "Lieferung r261.108 freigeben")
            tag_record.return_value = (self.source_sha, 41)
            with self.assertRaises(DeliveryError) as raised:
                run("repeat", issue=42)
            self.assertEqual(raised.exception.status, Status.FREIGABE_FAILED)


if __name__ == "__main__":
    unittest.main()
