from __future__ import annotations

import hashlib
import re
import tarfile
import unittest
from pathlib import Path


AUTOMATION_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = AUTOMATION_ROOT.parent

REFERENCE_HASHES = {
    "LBS_SVN_Hook_v0.4.bash": "ac50916676fe92f7d5ec2ff063d39382dfea06b9cb5ee8aa312afd431324cb33",
    "BYAUTOND.tgz": "877045df9b942c7573d52abd9544e542da1691432af75c41602ed7e0aa8b2c9b",
    "OSAUTONF.tgz": "c1d5026c84a5d8c348652b116da127b2cd9e1835e856f5af53a81dba8bbd6abc",
    "_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt": "9470daf483c3a2349853585d346a96efaa1f760e34b9614dbfc4a573a86369b4",
    "_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt": "f12458507ce0c3470865db918c922ee19b230b90b3ff40421d0a69cf9165d77e",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def info_archive_paths(path: Path) -> list[str]:
    result = []
    for line in path.read_text(encoding="ascii").splitlines():
        if re.fullmatch(r"[d-][rwx-]{9} .+", line):
            result.append(line.split(maxsplit=5)[5].rstrip("/"))
    return result


def direct_diff_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="ascii").splitlines()
        if re.match(r"^[AMD]\s+VORRELEASE/", line)
    ]


class ReferenceIntegrityTests(unittest.TestCase):
    def test_historical_sources_and_golden_masters_are_unchanged(self) -> None:
        for name, expected_hash in REFERENCE_HASHES.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(WORKSPACE_ROOT / name), expected_hash)

    def test_by_delta_structure_deletion_list_and_info_contract(self) -> None:
        archive_path = WORKSPACE_ROOT / "BYAUTOND.tgz"
        info_path = (
            WORKSPACE_ROOT
            / "_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt"
        )
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            files = [member for member in members if member.isfile()]
            directories = [member for member in members if member.isdir()]
            deletion_file = archive.extractfile("BYAUTOND.txt")
            self.assertIsNotNone(deletion_file)
            deletion_lines = deletion_file.read().decode("utf-8").splitlines()

        self.assertEqual((len(members), len(files), len(directories)), (65, 33, 32))
        self.assertTrue(all(not name.startswith("./") for name in names))
        self.assertIn("BYAUTOND.txt", names)
        self.assertTrue(
            all(
                name in {"BYAUTOND.txt", "LOMS_Autonom[BY]"}
                or name.startswith("LOMS_Autonom[BY]/")
                for name in names
            )
        )
        self.assertEqual(len([line for line in deletion_lines if line]), 12)
        self.assertTrue(
            all(line.startswith("LOMS_Autonom[BY]/") for line in deletion_lines)
        )
        self.assertEqual(info_archive_paths(info_path), names)

        diff_lines = direct_diff_lines(info_path)
        self.assertEqual(len(diff_lines), 14)
        self.assertEqual(sum(line.startswith("A") for line in diff_lines), 2)
        self.assertEqual(sum(line.startswith("M") for line in diff_lines), 12)
        self.assertEqual(sum(line.startswith("D") for line in diff_lines), 0)

    def test_os_full_structure_and_info_contract(self) -> None:
        archive_path = WORKSPACE_ROOT / "OSAUTONF.tgz"
        info_path = (
            WORKSPACE_ROOT
            / "_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt"
        )
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            files = [member for member in members if member.isfile()]
            directories = [member for member in members if member.isdir()]

        self.assertEqual(
            (len(members), len(files), len(directories)), (1017, 835, 182)
        )
        self.assertTrue(
            all(
                name == "./LOMS_Autonom[OS]"
                or name.startswith("./LOMS_Autonom[OS]/")
                for name in names
            )
        )
        self.assertEqual(info_archive_paths(info_path), names)

        diff_lines = direct_diff_lines(info_path)
        self.assertEqual(len(diff_lines), 15)
        self.assertEqual(sum(line.startswith("A") for line in diff_lines), 2)
        self.assertEqual(sum(line.startswith("M") for line in diff_lines), 3)
        self.assertEqual(sum(line.startswith("D") for line in diff_lines), 10)


if __name__ == "__main__":
    unittest.main()
