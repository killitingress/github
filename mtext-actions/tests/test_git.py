"""Prüft Git-Hilfen für Release-Diffs und Vorgängertags."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.git import changes, previous_tag

from tests.support import git, setup_repository


class GitTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt ein Repository mit einem Release-Tag."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Bereitstellung")
        git(self.repository, "tag", "R261.100")

    def test_previous_tag_returns_numeric_predecessor(self) -> None:
        """Ermittelt den letzten numerisch kleineren Release-Tag."""

        git(self.repository, "commit", "--allow-empty", "-m", "next")
        git(self.repository, "tag", "R261.108")
        self.assertEqual(previous_tag(self.repository, "R261.108"), "R261.100")

    def test_changes_parses_copy_like_rename(self) -> None:
        """Liest erkannte Dateikopien mit Quell- und Zielpfad."""

        project = self.repository / "LOMS_Basis"
        (project / "source.txt").write_text("same\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "source")
        base = git(self.repository, "rev-parse", "HEAD")
        shutil.copy(project / "source.txt", project / "target.txt")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "copy")

        copies = [
            item
            for item in changes(
                self.repository, base, git(self.repository, "rev-parse", "HEAD")
            )
            if item.status == "C"
        ]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].old_path, "LOMS_Basis/source.txt")
        self.assertEqual(copies[0].path, "LOMS_Basis/target.txt")


if __name__ == "__main__":
    unittest.main()
