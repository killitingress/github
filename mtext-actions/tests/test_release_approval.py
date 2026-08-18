"""Prüft Vorbereitung, Merge-Prüfung und Nachweis der Release-Freigabe."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from lbs_delivery.mainframe_release import build_release
from lbs_delivery.process import DeliveryError, NETWORK_TIMEOUT
from lbs_delivery.release_approval import (
    finalize_release_approval,
    prepare_release_approval,
    read_pull_request,
)

from tests.support import TempDirTestCase, git, jcl_template, load_test_configuration, setup_release_repository


class ReleaseApprovalTests(TempDirTestCase):
    """Prüft die Bindung von Pull Request, Lieferumfang und Release-Tag."""

    def setUp(self) -> None:
        """Bereitet einen noch nicht freigegebenen regulären Release-Stand vor."""

        super().setUp()
        self.repository = setup_release_repository(self.root)
        git(self.repository, "tag", "-d", "v261.108")
        self.source_sha = git(self.repository, "rev-parse", "HEAD")
        self.configuration = load_test_configuration(self.repository)

    def prepare(self) -> tuple[str, str]:
        """Erzeugt und committet eine Freigabeanforderung im Test-Repository."""

        approval_branch, path = prepare_release_approval(
            self.configuration,
            repository_root=self.repository,
            tag="v261.108",
            branch="release/R261",
            source_sha=self.source_sha,
            run_reference="123-1",
        )
        self.assertEqual(approval_branch, "release-approval/v261.108/123-1")
        git(self.repository, "add", str(path.relative_to(self.repository)))
        git(self.repository, "commit", "-m", "release approval")
        merge_sha = git(self.repository, "rev-parse", "HEAD")
        return approval_branch, merge_sha

    def merged_pull_request(self, approval_branch: str, merge_sha: str) -> dict[str, object]:
        """Baut die GitHub-Antwort eines regelkonform zusammengeführten Freigabe-PRs."""

        return {
            "merged": True,
            "merge_commit_sha": merge_sha,
            "base": {"ref": "release/R261"},
            "head": {"ref": approval_branch},
        }

    def test_prepares_project_element_lists(self) -> None:
        """Prüft den im Pull Request sichtbaren fachlichen Lieferumfang."""

        _, path = prepare_release_approval(
            self.configuration,
            repository_root=self.repository,
            tag="v261.108",
            branch="release/R261",
            source_sha=self.source_sha,
            run_reference="123-1",
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["release"], "v261.108")
        self.assertEqual(document["branch"], "release/R261")
        self.assertEqual(document["commit"], self.source_sha)
        project = document["projekte"][0]
        self.assertEqual(project["stand"]["von"]["referenz"], "v261.100")
        self.assertIn(["D", "deleted.txt"], project["elemente"])
        self.assertIn(["A", "new.txt"], project["elemente"])

        with self.assertRaisesRegex(DeliveryError, "regulären Release-Tag"):
            prepare_release_approval(
                self.configuration,
                repository_root=self.repository,
                tag="v261.108a",
                branch="release/R261",
                source_sha=self.source_sha,
                run_reference="123-1",
            )

    def test_finalizes_matching_pull_request(self) -> None:
        """Prüft Merge-Daten und den unveränderten freigegebenen Stand."""

        approval_branch, merge_sha = self.prepare()
        pull_request = self.merged_pull_request(approval_branch, merge_sha)
        tag = finalize_release_approval(
            self.configuration,
            repository_root=self.repository,
            approval_branch=approval_branch,
            branch="release/R261",
            merge_sha=merge_sha,
            pull_request=pull_request,
        )
        self.assertEqual(tag, "v261.108")

        pull_request["merged"] = False
        with self.assertRaisesRegex(DeliveryError, "nicht zusammengeführt"):
            finalize_release_approval(
                self.configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/R261",
                merge_sha=merge_sha,
                pull_request=pull_request,
            )

    def test_rejects_changed_delivery_after_approval(self) -> None:
        """Lehnt einen Merge ab, der über den Nachweis hinaus Projekte ändert."""

        approval_branch, _ = self.prepare()
        (self.repository / "LOMS_Basis/nachtraeglich.txt").write_text("spät\n", encoding="utf-8")
        git(self.repository, "add", "LOMS_Basis/nachtraeglich.txt")
        git(self.repository, "commit", "-m", "nachträgliche Änderung")
        merge_sha = git(self.repository, "rev-parse", "HEAD")

        with self.assertRaisesRegex(DeliveryError, "nach der Freigabe geändert"):
            finalize_release_approval(
                self.configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/R261",
                merge_sha=merge_sha,
                pull_request=self.merged_pull_request(approval_branch, merge_sha),
            )

    def test_rejects_pull_request_of_another_branch(self) -> None:
        """Lehnt einen Merge ab, der nicht in den gemeldeten Lieferbranch führte."""

        approval_branch, merge_sha = self.prepare()
        pull_request = self.merged_pull_request(approval_branch, merge_sha)
        pull_request["base"] = {"ref": "main"}
        with self.assertRaisesRegex(DeliveryError, "anderen Branch zusammengeführt"):
            finalize_release_approval(
                self.configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/R261",
                merge_sha=merge_sha,
                pull_request=pull_request,
            )

    def test_rejects_tampered_approval_document(self) -> None:
        """Lehnt einen Nachweis ab, dessen Elementliste nicht zum Lieferumfang passt."""

        approval_branch, merge_sha = self.prepare()
        path = self.repository / ".github" / "release-approvals" / "v261.108.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["projekte"][0]["elemente"].append(["A", "manipuliert.txt"])
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        git(self.repository, "add", str(path.relative_to(self.repository)))
        git(self.repository, "commit", "--amend", "--no-edit")

        merge_sha = git(self.repository, "rev-parse", "HEAD")
        with self.assertRaisesRegex(DeliveryError, "passt nicht zum Lieferumfang"):
            finalize_release_approval(
                self.configuration,
                repository_root=self.repository,
                approval_branch=approval_branch,
                branch="release/R261",
                merge_sha=merge_sha,
                pull_request=self.merged_pull_request(approval_branch, merge_sha),
            )

    def test_reads_pull_request_with_technical_identity(self) -> None:
        """Prüft GitHub-Endpunkt, Token und Zeitüberschreitung des externen Aufrufs."""

        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"merged": True, "merge_commit_sha": "1" * 40}
        ).encode()
        with patch("lbs_delivery.github_api.urllib.request.urlopen", return_value=response) as urlopen:
            document = read_pull_request(
                api_url="https://github.example/api/v3",
                repository="FinanzInformatik/mandant",
                number=17,
                token="secret",
            )

        self.assertTrue(document["merged"])
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://github.example/api/v3/repos/FinanzInformatik/mandant/pulls/17",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], NETWORK_TIMEOUT)

    def test_regular_release_requires_matching_approval(self) -> None:
        """Lehnt einen direkten regulären Tag ab und akzeptiert den Freigabe-Merge."""

        git(self.repository, "tag", "v261.108", self.source_sha)
        git(self.repository, "checkout", "--detach", "v261.108")
        with self.assertRaisesRegex(DeliveryError, "keine PR-Freigabe"):
            build_release(
                self.configuration,
                repository_root=self.repository,
                output_directory=self.root / "rejected",
                jcl_template=jcl_template(),
                tag="v261.108",
                trigger_sha=self.source_sha,
            )

        git(self.repository, "checkout", "release/R261")
        git(self.repository, "tag", "-d", "v261.108")
        _, merge_sha = self.prepare()
        git(self.repository, "update-ref", "refs/remotes/origin/release/R261", merge_sha)
        git(self.repository, "tag", "v261.108", merge_sha)
        git(self.repository, "checkout", "--detach", "v261.108")
        build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.root / "accepted",
            jcl_template=jcl_template(),
            tag="v261.108",
            trigger_sha=merge_sha,
        )


if __name__ == "__main__":
    unittest.main()
