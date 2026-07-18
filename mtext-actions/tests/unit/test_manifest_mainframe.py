from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from lbs_delivery.errors import DeliveryError
from lbs_delivery.mainframe import FtpSettings, render_package_jcl, submit_package
from lbs_delivery.manifest import verify_artifacts, write_manifest
from lbs_delivery.mtext_adapter import call_adapter
from lbs_delivery.paths import sha256_file
from lbs_delivery.resources import publish_server_sync, stage_resources


# Wurzel des zentralen Automationsprojekts mit dem versionierten JCL-Template.
ROOT = Path(__file__).resolve().parents[2]


class UebergabeVertragTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt den kleinsten vollständigen Manifestvertrag je Test."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / "FIBASISF.tgz"
        self.information = self.root / "_INFO.txt"
        self.package.write_bytes(b"package")
        self.information.write_text("info\n", encoding="utf-8")
        self.package_artifact = {
            "kind": "package",
            "path": self.package.name,
            "project": "LOMS_Basis",
            "size": self.package.stat().st_size,
            "sha256": sha256_file(self.package),
            "member": "FIBASISF",
            "project_code": "BASIS",
            "deletion_list": None,
            "deletion_count": 0,
        }
        self.manifest = {
            "repository": "mtext-fi",
            "mandant": "FI",
            "release_tag": "R261.100",
            "releaselinie": "R261",
            "delivery_type": "FULL",
            "base_tag": None,
            "base_sha": None,
            "target_sha": "a" * 40,
            "previous_tag": None,
            "previous_sha": None,
            "artifacts": [
                self.package_artifact,
                {
                    "kind": "information",
                    "path": self.information.name,
                    "project": "LOMS_Basis",
                    "size": self.information.stat().st_size,
                    "sha256": sha256_file(self.information),
                },
            ],
            "jcl": {
                "ISPW": "P",
                "LEVEL": "FKTE",
                "SUBSYS": "LOMS",
                "ASSIGNMENT": "LOMS000066",
            },
        }

    def test_resources_and_adapter(self) -> None:
        """Prüft Ressourcenveröffentlichung und unmittelbare Adapterannahme."""

        source = self.root / "source"
        staging = self.root / "staging"
        server_sync = self.root / "serverSync"
        (source / "LOMS_Basis").mkdir(parents=True)
        (source / "LOMS_Basis/value.txt").write_text("new", encoding="utf-8")
        (server_sync / "LOMS_Basis").mkdir(parents=True)
        (server_sync / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")

        # Staging und Veröffentlichung ersetzen den vorhandenen Projektstand.
        projects = ["LOMS_Basis"]
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

    def test_manifest_validation_and_tampering(self) -> None:
        """Prüft Manifestregeln und nachträgliche Artefaktänderungen."""

        write_manifest(self.root / "manifest.json", self.manifest)
        verify_artifacts(self.manifest, self.root)

        invalid_changes = (
            ("jcl", "LEVEL", "DEV"),
            (None, "mandant", "XX"),
            ("package", "member", "TOO_LONG9"),
            (None, "unexpected", True),
        )
        for container, field, value in invalid_changes:
            with self.subTest(field=field, value=value):
                invalid = {
                    **self.manifest,
                    "jcl": dict(self.manifest["jcl"]),
                    "artifacts": [dict(item) for item in self.manifest["artifacts"]],
                }
                if container == "jcl":
                    invalid["jcl"][field] = value
                elif container == "package":
                    invalid["artifacts"][0][field] = value
                else:
                    invalid[field] = value
                with self.assertRaises(DeliveryError):
                    write_manifest(self.root / "invalid.json", invalid)

        # Eine Inhaltsänderung nach dem Build muss an der Publish-Grenze auffallen.
        self.package.write_bytes(b"tampered")
        with self.assertRaises(DeliveryError):
            verify_artifacts(self.manifest, self.root)

    def test_mainframe_submission(self) -> None:
        """Prüft Paketupload und JES-Annahme mit einem kontrollierten FTP-Client."""

        template = (ROOT / "templates/mainframe-upload.jcl").read_text(
            encoding="ascii"
        )
        invalid_manifest = {
            **self.manifest,
            "jcl": {**self.manifest["jcl"], "LEVEL": "DEV"},
        }
        with self.assertRaises(DeliveryError) as raised:
            render_package_jcl(invalid_manifest, self.package_artifact, template)
        self.assertIn("ungültiger Wert für LEVEL", str(raised.exception))

        jcl = self.root / "FIBASISF.jcl"
        jcl.write_text(
            render_package_jcl(self.manifest, self.package_artifact, template),
            encoding="ascii",
        )
        ftp = MagicMock()
        ftp.login.return_value = "230 logged in"
        ftp.storbinary.return_value = "250 stored"
        ftp.sendcmd.return_value = "200 site ok"
        ftp.storlines.return_value = "250 submitted"
        ftp.quit.return_value = "221 bye"
        submit_package(
            self.package,
            jcl,
            "FIBASISF",
            FtpSettings("host", "user", "password"),
            ftp_factory=lambda: ftp,
        )
        ftp.connect.assert_called_once_with("host", timeout=60.0)
        self.assertEqual(
            ftp.storbinary.call_args.args[0],
            "STOR 'IEA.LOMS.TONICZ(FIBASISF)'",
        )
        ftp.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
        self.assertEqual(ftp.storlines.call_args.args[0], "STOR LIT9028A")


if __name__ == "__main__":
    unittest.main()
