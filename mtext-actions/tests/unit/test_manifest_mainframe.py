from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from lbs_delivery.errors import DeliveryError
from lbs_delivery.mainframe import FtpSettings, render_package_jcl, submit_package
from lbs_delivery.manifest import sha256_file, verify_artifacts, write_manifest
from lbs_delivery.mtext_adapter import call_adapter
from lbs_delivery.resources import publish_server_sync, stage_resources


ROOT = Path(__file__).resolve().parents[2]


class HandoverContractTests(unittest.TestCase):
    def test_resource_adapter_and_mainframe_handover(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            staging = root / "staging"
            server_sync = root / "serverSync"
            (source / "LOMS_Basis").mkdir(parents=True)
            (source / "LOMS_Basis/value.txt").write_text("new", encoding="utf-8")
            (server_sync / "LOMS_Basis").mkdir(parents=True)
            (server_sync / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")

            projects = [{"name": "LOMS_Basis", "source_path": "LOMS_Basis"}]
            self.assertEqual(stage_resources(source, staging, projects), ["LOMS_Basis"])
            publish_server_sync(staging, server_sync)
            self.assertEqual(
                (server_sync / "LOMS_Basis/value.txt").read_text(encoding="utf-8"),
                "new",
            )

            response = call_adapter(
                "https://adapter.example.test/vMtextAdapter/sync",
                {"mandant": "MAN", "institut": "INR"},
                opener=lambda *_args, **_kwargs: nullcontext(
                    SimpleNamespace(status=200, read=lambda _: b"accepted")
                ),
            )
            self.assertEqual((response.status, response.body), (200, "accepted"))

            package = root / "FIBASISF.tgz"
            information = root / "_INFO.txt"
            package.write_bytes(b"package")
            information.write_text("info\n", encoding="utf-8")
            package_artifact = {
                "kind": "package",
                "path": package.name,
                "project": "LOMS_Basis",
                "size": package.stat().st_size,
                "sha256": sha256_file(package),
                "member": "FIBASISF",
                "project_code": "BASIS",
                "deletion_list": None,
                "deletion_count": 0,
            }
            manifest = {
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
                    package_artifact,
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
            write_manifest(root / "manifest.json", manifest)
            verify_artifacts(manifest, root)
            package.write_bytes(b"tampered")
            with self.assertRaises(DeliveryError):
                verify_artifacts(manifest, root)
            package.write_bytes(b"package")

            template = (ROOT / "templates/mainframe-upload.jcl").read_text(
                encoding="ascii"
            )
            jcl = root / "FIBASISF.jcl"
            jcl.write_text(
                render_package_jcl(manifest, package_artifact, template),
                encoding="ascii",
            )
            ftp = MagicMock()
            ftp.login.return_value = "230 logged in"
            ftp.storbinary.return_value = "250 stored"
            ftp.sendcmd.return_value = "200 site ok"
            ftp.storlines.return_value = "250 submitted"
            ftp.quit.return_value = "221 bye"
            submit_package(
                package,
                jcl,
                "FIBASISF",
                FtpSettings("host", "user", "password"),
                ftp_factory=lambda: ftp,
            )
            ftp.connect.assert_called_once_with("host", timeout=60.0)
            self.assertEqual(ftp.storbinary.call_args.args[0], "STOR 'IEA.LOMS.TONICZ(FIBASISF)'")
            ftp.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
            self.assertEqual(ftp.storlines.call_args.args[0], "STOR LIT9028A")


if __name__ == "__main__":
    unittest.main()
