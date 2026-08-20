"""Prüft Vorbereitung, Vorprüfung und Abschluss der Release-Freigabe."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from lbs_delivery.config import load_configuration
from lbs_delivery.mainframe_release import _build_release
from lbs_delivery.process import DeliveryError
from lbs_delivery.release_approval import (
    _check_release_approval,
    _finalize_release_approval,
    _prepare_release_approval,
)

from tests.support import TempDirTestCase, git, jcl_template, load_test_configuration, setup_release_repository


class ReleaseApprovalTests(TempDirTestCase):
    """Prüft Release-Version, Pull-Request-Daten und sichtbaren Lieferumfang."""

    def setUp(self) -> None:
        """Bereitet einen noch nicht freigegebenen Release-Stand vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        git(self.repository, "tag", "-d", "v261.108")
        self.configuration = load_test_configuration(self.repository)
        git(self.repository, "add", ".github/config.json")
        git(self.repository, "commit", "-m", "Mandantenkonfiguration")
        git(self.repository, "update-ref", "refs/remotes/origin/release/261", "HEAD")
        self.source_sha = git(self.repository, "rev-parse", "HEAD")

    def prepare(self) -> tuple[str, str]:
        """Aktualisiert und committet die Release-Version im Test-Repository."""

        approval_branch, path = _prepare_release_approval(
            self.configuration,
            repository_root=self.repository,
            tag="v261.108",
            branch="release/261",
            source_sha=self.source_sha,
            run_reference="123-1",
        )
        self.assertEqual(approval_branch, "release-approval/v261.108/123-1")
        git(self.repository, "add", str(path.relative_to(self.repository)))
        git(self.repository, "commit", "-m", "Release zur Freigabe vorlegen")
        return approval_branch, git(self.repository, "rev-parse", "HEAD")

    def merged_pull_request(self, approval_branch: str, merge_sha: str) -> dict[str, object]:
        """Baut die GitHub-Antwort eines zusammengeführten Freigabe-PRs."""

        return {
            "merged": True,
            "merge_commit_sha": merge_sha,
            "base": {"ref": "release/261"},
            "head": {"ref": approval_branch},
        }

    def test_prepares_release_version(self) -> None:
        """Schreibt die gewählte Version als einzige fachliche Freigabeangabe."""

        approval_branch, path = _prepare_release_approval(
            self.configuration,
            repository_root=self.repository,
            tag="v261.108",
            branch="release/261",
            source_sha=self.source_sha,
            run_reference="123-1",
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(approval_branch, "release-approval/v261.108/123-1")
        self.assertEqual(document["mandant"]["letztes_release"], "v261.108")

        with self.assertRaisesRegex(DeliveryError, "ohne Buchstabensuffix"):
            _prepare_release_approval(
                self.configuration,
                repository_root=self.repository,
                tag="v261.108a",
                branch="release/261",
                source_sha=self.source_sha,
                run_reference="123-1",
            )

    def test_shows_release_scope_in_check_summary(self) -> None:
        """Zeigt Stand, Lieferart, Änderungen und Löschungen im Pull Request."""

        approval_branch, target_sha = self.prepare()
        configuration = load_configuration(self.repository, self.configuration.repository)
        summary = _check_release_approval(
            configuration,
            repository_root=self.repository,
            approval_branch=approval_branch,
            branch="release/261",
            target_sha=target_sha,
        )
        self.assertIn("## Release-Vorprüfung", summary)
        self.assertIn("`DELTA`", summary)
        self.assertIn("`v261.100`", summary)
        self.assertIn("`D` `deleted.txt`", summary)
        self.assertIn("`A` `new.txt`", summary)

    def test_check_rejects_inconsistent_release_state(self) -> None:
        """Lehnt einen abweichenden Checkout, eine andere Version und vorhandene Tags ab."""

        approval_branch, target_sha = self.prepare()
        configuration = load_configuration(self.repository, self.configuration.repository)

        with self.assertRaisesRegex(DeliveryError, "andere Release-Version"):
            _check_release_approval(
                replace(configuration, letztes_release="v261.107"),
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                target_sha=target_sha,
            )

        git(self.repository, "tag", "v261.108", target_sha)
        with self.assertRaisesRegex(DeliveryError, "bereits vorhanden"):
            _check_release_approval(
                configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                target_sha=target_sha,
            )
        git(self.repository, "tag", "-d", "v261.108")

        git(self.repository, "checkout", "--detach", self.source_sha)
        with self.assertRaisesRegex(DeliveryError, "Checkout stimmt nicht"):
            _check_release_approval(
                configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                target_sha=target_sha,
            )

    def test_finalizes_matching_pull_request(self) -> None:
        """Ordnet Merge, Zielbranch und eingetragene Release-Version einander zu."""

        approval_branch, merge_sha = self.prepare()
        configuration = load_configuration(self.repository, self.configuration.repository)
        pull_request = self.merged_pull_request(approval_branch, merge_sha)
        tag = _finalize_release_approval(
            configuration,
            repository_root=self.repository,
            approval_branch=approval_branch,
            branch="release/261",
            merge_sha=merge_sha,
            pull_request=pull_request,
        )
        self.assertEqual(tag, "v261.108")

        pull_request["merged"] = False
        with self.assertRaisesRegex(DeliveryError, "nicht zusammengeführt"):
            _finalize_release_approval(
                configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                merge_sha=merge_sha,
                pull_request=pull_request,
            )

    def test_rejects_mismatched_pull_request(self) -> None:
        """Lehnt einen anderen Zielbranch oder eine andere Release-Version ab."""

        approval_branch, merge_sha = self.prepare()
        configuration = load_configuration(self.repository, self.configuration.repository)
        pull_request = self.merged_pull_request(approval_branch, merge_sha)
        pull_request["base"] = {"ref": "main"}
        with self.assertRaisesRegex(DeliveryError, "anderen Branch zusammengeführt"):
            _finalize_release_approval(
                configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                merge_sha=merge_sha,
                pull_request=pull_request,
            )

        configuration = load_test_configuration(self.repository, mandant={"letztes_release": "v261.107"})
        with self.assertRaisesRegex(DeliveryError, "andere Release-Version"):
            _finalize_release_approval(
                configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/261",
                merge_sha=merge_sha,
                pull_request=self.merged_pull_request(approval_branch, merge_sha),
            )

    def test_regular_release_requires_matching_last_release(self) -> None:
        """Bindet reguläre Lieferungen an die im getaggten Stand genannte Version."""

        git(self.repository, "tag", "v261.108", self.source_sha)
        git(self.repository, "checkout", "--detach", "v261.108")
        with self.assertRaisesRegex(DeliveryError, "andere freigegebene Release-Version"):
            _build_release(
                self.configuration,
                repository_root=self.repository,
                output_directory=self.root / "rejected-release",
                jcl_template=jcl_template(),
                tag="v261.108",
                trigger_sha=self.source_sha,
            )

        configuration = replace(self.configuration, letztes_release="v261.108")
        _build_release(
            configuration,
            repository_root=self.repository,
            output_directory=self.root / "release",
            jcl_template=jcl_template(),
            tag="v261.108",
            trigger_sha=self.source_sha,
        )


if __name__ == "__main__":
    unittest.main()
