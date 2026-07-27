"""Prüft den vollständigen Vertrag für FULL, DELTA, Manifest und Übergabe.

Die Tests verwenden eine echte Git-Historie und echte Archive. Lediglich der
externe Mainframe-Transfer wird ersetzt, damit die lokalen Vertrauensgrenzen
weiterhin geprüft werden.
"""

from __future__ import annotations

import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.manifest import load_and_verify, sha256_file
from lbs_delivery.process import DeliveryError, Status
from lbs_delivery.release import build_release

from tests.support import (
    AUTOMATION_ROOT,
    git,
    load_test_configuration,
    setup_release_repository,
)


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt eine mit Release-Tags versehene Historie und lädt ihre geprüfte Konfiguration.

        Jeder Test beginnt mit demselben FULL-Ausgangsstand, direkten Vorgänger
        und DELTA-Ziel. Paketvergleiche bleiben dadurch reproduzierbar.
        """

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_release_repository(self.root)
        self.configuration = load_test_configuration(self.repository)

    def test_builds_reproducible_full_and_delta_archives(self) -> None:
        """Prüft reproduzierbare Archive, Manifestdaten und gerenderte JCL.

        Der zweimalige Bau desselben DELTA belegt die Reproduzierbarkeit. Weitere
        Prüfungen decken Löschbeleg, Aufbau des FULL-Pakets und die geprüfte
        Übergabe an die ersetzte Mainframe-Grenze ab.
        """

        target_sha = git(self.repository, "rev-parse", "HEAD")
        first = self.root / "first"
        second = self.root / "second"
        first_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=first,
            tag="R261.108",
            trigger_sha=target_sha,
        )
        second_manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=second,
            tag="R261.108",
            trigger_sha=target_sha,
        )
        first_manifest, packages = load_and_verify(first_manifest_path, first)
        second_manifest, _ = load_and_verify(second_manifest_path, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(sha256_file(first / "FIBASISD.tgz"), sha256_file(second / "FIBASISD.tgz"))
        self.assertEqual([item["member"] for item in packages], ["FIBASISD"])

        with tarfile.open(first / "FIBASISD.tgz", "r:gz") as archive:
            names = archive.getnames()
            deletion = archive.extractfile("FIBASISD.txt")
            self.assertIsNotNone(deletion)
            deleted = deletion.read().decode("utf-8")
        self.assertIn("LOMS_Basis/new.txt", names)
        self.assertIn("LOMS_Basis/deleted.txt", deleted)

        with (
            patch.dict(
                os.environ,
                {
                    "MAINFRAME_FTP_HOST": "mainframe.example",
                    "MAINFRAME_FTP_USER": "user",
                    "MAINFRAME_FTP_PASSWORD": "password",
                },
            ),
            patch("lbs_delivery.mainframe.submit_package") as submit,
        ):
            result = publish_mainframe(
                manifest_path=first_manifest_path,
                artifact_root=first,
                template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
                temporary_directory=self.root / "jcl",
            )
        self.assertEqual(result["status"], Status.MAINFRAME_SUBMITTED.value)
        submit.assert_called_once()
        rendered = (self.root / "jcl/FIBASISD.jcl").read_text(encoding="ascii")
        self.assertIn("MEMBER=((FIBASISD,,R))", rendered)
        self.assertNotIn("@@", rendered)

        git(self.repository, "checkout", "--detach", "R261.100")
        full_manifest = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=self.root / "full",
            tag="R261.100",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        _manifest, full_packages = load_and_verify(full_manifest, self.root / "full")
        self.assertEqual([package["member"] for package in full_packages], ["FIBASISF", "FIBASISD"])

    def test_rejects_tampered_release_artifact(self) -> None:
        """Lehnt ein Paket ab, das nach Erzeugung des Manifests verändert wurde.

        Die Übergabe verlässt sich auf das Manifest als Integritätsgrenze.
        Abweichungen bei Prüfsumme oder Größe müssen das Artefakt deshalb vor dem
        Transfer stoppen.
        """

        output = self.root / "tampered"
        manifest_path = build_release(
            self.configuration,
            repository_root=self.repository,
            output_directory=output,
            tag="R261.108",
            trigger_sha=git(self.repository, "rev-parse", "HEAD"),
        )
        (output / "FIBASISD.tgz").write_bytes(b"tampered")
        with self.assertRaises(DeliveryError):
            load_and_verify(manifest_path, output)


if __name__ == "__main__":
    unittest.main()
