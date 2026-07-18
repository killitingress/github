"""Prüft Git-Vorbedingungen für Sync und Release."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status
from lbs_delivery.git import changes, previous_tag, require_checkout, require_release_tag

from tests.support import git, setup_repository, track_remote_branch


class GitPreconditionTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt einen getaggten Bereitstellungsstand mit Remote-Referenz."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_repository(self.root, branch="R261/Bereitstellung")
        git(self.repository, "tag", "R261.100")
        track_remote_branch(self.repository, "R261/Bereitstellung")
        self.commit = git(self.repository, "rev-parse", "HEAD")

    def test_require_release_tag_accepts_checked_out_tag(self) -> None:
        """Akzeptiert einen gültigen Tag auf dem aktuellen Checkout."""

        git(self.repository, "checkout", "--detach", "R261.100")
        target = require_release_tag(
            self.repository, "R261.100", "R261/Bereitstellung"
        )
        self.assertEqual(target, self.commit)

    def test_require_release_tag_rejects_invalid_format(self) -> None:
        """Lehnt Tags außerhalb des Release-Formats ab."""

        with self.assertRaises(DeliveryError) as context:
            require_release_tag(
                self.repository, "invalid", "R261/Bereitstellung"
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_require_release_tag_rejects_wrong_checkout(self) -> None:
        """Lehnt ab, wenn HEAD nicht auf dem Zieltag steht."""

        project = self.repository / "LOMS_Basis"
        (project / "later.txt").write_text("later\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "after-tag")
        with self.assertRaises(DeliveryError) as context:
            require_release_tag(
                self.repository, "R261.100", "R261/Bereitstellung"
            )
        self.assertEqual(context.exception.status, Status.SOURCE_FAILED)

    def test_require_checkout_rejects_wrong_commit(self) -> None:
        """Lehnt Commits ab, die nicht dem aktuellen Checkout entsprechen."""

        git(self.repository, "checkout", "--detach", "R261.100")
        with self.assertRaises(DeliveryError) as context:
            require_checkout(
                self.repository,
                "0" * 40,
                "R261/Bereitstellung",
            )
        self.assertEqual(context.exception.status, Status.SOURCE_FAILED)

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
            for item in changes(self.repository, base, git(self.repository, "rev-parse", "HEAD"))
            if item.status == "C"
        ]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].old_path, "LOMS_Basis/source.txt")
        self.assertEqual(copies[0].path, "LOMS_Basis/target.txt")


if __name__ == "__main__":
    unittest.main()
