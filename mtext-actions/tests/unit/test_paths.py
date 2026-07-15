from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lbs_delivery.errors import DeliveryError, Status
from lbs_delivery.paths import reject_symlinks, resolve_within


class PathSafetyTests(unittest.TestCase):
    def test_traversal_and_symlinks_are_rejected_consistently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            outside = root / "outside"
            project = repository / "Project"
            project.mkdir(parents=True)
            outside.mkdir()
            (outside / "value.txt").write_text("outside", encoding="utf-8")

            with self.assertRaises(DeliveryError):
                resolve_within(
                    repository,
                    "../outside/value.txt",
                    status=Status.VALIDATION_FAILED,
                    subject="test",
                )

            link = project / "link.txt"
            link.symlink_to(outside / "value.txt")
            with self.assertRaises(DeliveryError):
                resolve_within(
                    repository,
                    "Project/link.txt",
                    status=Status.PACKAGE_FAILED,
                    subject="test",
                    reject_symlink=True,
                )
            with self.assertRaises(DeliveryError):
                reject_symlinks(
                    project, status=Status.PACKAGE_FAILED, subject="test"
                )


if __name__ == "__main__":
    unittest.main()
