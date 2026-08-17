"""Prüft die Tag-Reihenfolge für Beta-Lieferstände."""

from __future__ import annotations

import unittest
from pathlib import Path

from lbs_delivery import git as git_module

from tests.support import TempDirTestCase, git, init_repository


def setup_beta_tag_repository(root: Path) -> Path:
    """Legt eine Release-Tagfolge mit Beta-Suffixen an."""

    repository = init_repository(root, branch="release/R261")
    for message, tag in (
        ("full", "v261.100"),
        ("previous", "v261.107"),
        ("beta-a", "v261.108a"),
        ("beta-b", "v261.108b"),
        ("release", "v261.108"),
    ):
        git(repository, "commit", "--allow-empty", "-m", message)
        git(repository, "tag", tag)
    return repository


class PreviousTagTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = setup_beta_tag_repository(self.root)

    def test_beta_tag_predecessors(self) -> None:
        """Beta-Tags und der reguläre Tag bilden eine gemeinsame Vorgängerfolge."""

        self.assertEqual(git_module.previous_tag(self.repository, "v261.108a"), "v261.107")
        self.assertEqual(git_module.previous_tag(self.repository, "v261.108b"), "v261.108a")
        self.assertEqual(git_module.previous_tag(self.repository, "v261.108"), "v261.108b")


if __name__ == "__main__":
    unittest.main()
