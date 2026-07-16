from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.cli import build_parser, run
from lbs_delivery.errors import DeliveryError
from lbs_delivery.mainframe import FtpSettings, submit_package
from lbs_delivery.manifest import load_manifest, sha256_file, verify_artifacts, write_manifest


ROOT = Path(__file__).resolve().parents[2]


class _FakeFtp:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def connect(self, host: str, timeout: float) -> str:
        self.commands.append(f"CONNECT {host} {timeout}")
        return "220 ready"

    def login(self, user: str, password: str) -> str:
        self.commands.append(f"LOGIN {user} <redacted>")
        return "230 logged in"

    def storbinary(self, command: str, source: object) -> str:
        self.commands.append(command)
        return "250 stored"

    def sendcmd(self, command: str) -> str:
        self.commands.append(command)
        return "200 site ok"

    def storlines(self, command: str, source: object) -> str:
        self.commands.append(command)
        return "250 submitted"

    def quit(self) -> str:
        self.commands.append("QUIT")
        return "221 bye"

    def close(self) -> None:
        self.commands.append("CLOSE")


def release_manifest(root: Path) -> dict:
    package = root / "FIBASISF.tgz"
    information = root / "_INFO.txt"
    package.write_bytes(b"package")
    information.write_text("info\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "repository": "mtext-fi",
        "mandant": "FI",
        "release_tag": "R261.100",
        "release_line": "R261",
        "delivery_type": "FULL",
        "base_tag": None,
        "base_sha": None,
        "target_sha": "a" * 40,
        "previous_tag": None,
        "previous_sha": None,
        "artifacts": [
            {
                "kind": "package",
                "path": package.name,
                "project": "LOMS_Basis",
                "size": package.stat().st_size,
                "sha256": sha256_file(package),
                "member": "FIBASISF",
                "project_code": "BASIS",
                "deletion_list": None,
                "deletion_count": 0,
            },
            {
                "kind": "information",
                "path": information.name,
                "project": "LOMS_Basis",
                "size": information.stat().st_size,
                "sha256": sha256_file(information),
            },
        ],
        "jcl": {
            "ISPW": "P",
            "LEVEL": "FKTE",
            "SUBSYS": "LOMS",
            "ASSIGNMENT": "LOMS000066",
        },
    }


class ManifestAndMainframeTests(unittest.TestCase):
    def test_checksum_verification_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = release_manifest(root)
            verify_artifacts(manifest, root)
            (root / "FIBASISF.tgz").write_bytes(b"tampered")
            with self.assertRaises(DeliveryError):
                verify_artifacts(manifest, root)

    def test_manifest_schema_rejects_invalid_package_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            write_manifest(manifest_path, release_manifest(root))
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["artifacts"][0]["member"] = "TOO-LONG-MEMBER"
            manifest_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(DeliveryError):
                load_manifest(manifest_path)

    def test_manifest_semantics_reject_cross_field_inconsistencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = release_manifest(root)
            invalid_documents = []

            wrong_base = copy.deepcopy(valid)
            wrong_base.update(
                delivery_type="DELTA",
                base_tag="R261.101",
                base_sha="b" * 40,
            )
            wrong_base["artifacts"][0]["deletion_list"] = "FIBASISD.txt"
            invalid_documents.append(wrong_base)

            mismatched_project = copy.deepcopy(valid)
            mismatched_project["artifacts"][1]["project"] = "LOMS_PKA"
            invalid_documents.append(mismatched_project)

            full_with_deletions = copy.deepcopy(valid)
            full_with_deletions["artifacts"][0]["deletion_list"] = "FIBASISD.txt"
            invalid_documents.append(full_with_deletions)

            delta_without_deletion_list = copy.deepcopy(valid)
            delta_without_deletion_list.update(
                delivery_type="DELTA",
                base_tag="R261.100",
                base_sha="b" * 40,
            )
            invalid_documents.append(delta_without_deletion_list)

            for index, document in enumerate(invalid_documents):
                with self.subTest(case=index), self.assertRaises(DeliveryError):
                    write_manifest(root / f"invalid-{index}.json", document)

    def test_publish_without_execute_only_verifies_and_renders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            write_manifest(manifest_path, release_manifest(root))
            temporary = root / "jcl"
            arguments = build_parser().parse_args(
                [
                    "publish-mainframe",
                    "--manifest",
                    str(manifest_path),
                    "--artifact-root",
                    str(root),
                    "--template",
                    str(ROOT / "templates/mainframe-upload.jcl"),
                    "--deployments-config",
                    str(ROOT / "config/deployments.json"),
                    "--deployments-schema",
                    str(ROOT / "config/deployments.schema.json"),
                    "--temporary-dir",
                    str(temporary),
                ]
            )
            with contextlib.redirect_stdout(io.StringIO()):
                status = run(arguments)
            self.assertEqual(status.value, "ARTIFACT_READY")
            self.assertTrue((temporary / "FIBASISF.jcl").is_file())

    def test_ftp_and_jes_contract_has_no_polling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "FIBASISF.tgz"
            jcl = root / "FIBASISF.jcl"
            package.write_bytes(b"package")
            jcl.write_bytes(b"//JOB\n")
            fake = _FakeFtp()
            submit_package(
                package,
                jcl,
                "FIBASISF",
                FtpSettings("host", "user", "password"),
                ftp_factory=lambda: fake,
            )
            self.assertIn("CONNECT host 60.0", fake.commands)
            self.assertIn("STOR 'IEA.LOMS.TONICZ(FIBASISF)'", fake.commands)
            self.assertIn("SITE FILETYPE=JES", fake.commands)
            self.assertIn("STOR LIT9028A", fake.commands)
            self.assertFalse(any("POLL" in command for command in fake.commands))


if __name__ == "__main__":
    unittest.main()
