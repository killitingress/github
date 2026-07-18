"""Prüft Ressourcensynchronisation und unmittelbare FTP-/JES-Übergabe."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from lbs_delivery.errors import DeliveryError, Status
from lbs_delivery.mainframe import submit_package
from lbs_delivery.sync import call_adapter, publish_server_sync, sync_resources

from tests.support import git, load_test_configuration, setup_sync_repository


class SyncAndMainframeTests(unittest.TestCase):
    def setUp(self) -> None:
        """Erzeugt einen erreichbaren Entwicklungscommit und seine Konfiguration."""

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = setup_sync_repository(self.root)
        self.configuration = load_test_configuration(self.root, self.repository)

    def test_sync_stages_and_replaces_complete_project(self) -> None:
        """Prüft den linearen lokalen Teil der Ressourcensynchronisation."""

        staging = self.root / "staging"
        result = sync_resources(
            self.configuration,
            repository_root=self.repository,
            commit=git(self.repository, "rev-parse", "HEAD"),
            source_branch="R261/Entwicklung",
            environment="Entwicklung",
            staging_root=staging,
            timeout=60.0,
            execute=False,
        )
        self.assertEqual(result["projects"], ["LOMS_Basis"])
        target = self.root / "serverSync"
        (target / "LOMS_Basis").mkdir(parents=True)
        (target / "LOMS_Basis/value.txt").write_text("old", encoding="utf-8")
        publish_server_sync(staging, target)
        self.assertEqual(
            (target / "LOMS_Basis/value.txt").read_text(encoding="utf-8"),
            "new",
        )

        status, body = call_adapter(
            "https://adapter.example.invalid/sync",
            timeout=1.0,
            opener=lambda *_args, **_kwargs: nullcontext(
                SimpleNamespace(status=200, read=lambda _limit: b"accepted")
            ),
        )
        self.assertEqual((status, body), (200, "accepted"))

    def test_sync_rejects_branch_environment_mismatch(self) -> None:
        """Lehnt Kombinationen aus Branch und Zielumgebung ab."""

        with self.assertRaises(DeliveryError) as context:
            sync_resources(
                self.configuration,
                repository_root=self.repository,
                commit=git(self.repository, "rev-parse", "HEAD"),
                source_branch="R261/Entwicklung",
                environment="Abnahme",
                staging_root=self.root / "staging",
                timeout=60.0,
                execute=False,
            )
        self.assertEqual(context.exception.status, Status.VALIDATION_FAILED)

    def test_ftp_uses_existing_mainframe_contract(self) -> None:
        """Prüft Dataset, Member und JES-Ziel ohne eigene Antwortauswertung."""

        package = self.root / "FIBASISF.tgz"
        jcl = self.root / "FIBASISF.jcl"
        package.write_bytes(b"package")
        jcl.write_bytes(b"//JCL\n")
        ftp = MagicMock()
        submit_package(
            package,
            jcl,
            "FIBASISF",
            host="host",
            user="user",
            password="password",
            ftp_factory=lambda: ftp,
        )
        ftp.connect.assert_called_once_with("host", timeout=60.0)
        ftp.login.assert_called_once_with("user", "password")
        self.assertEqual(
            ftp.storbinary.call_args.args[0],
            "STOR 'IEA.LOMS.TONICZ(FIBASISF)'",
        )
        ftp.sendcmd.assert_called_once_with("SITE FILETYPE=JES")
        self.assertEqual(ftp.storlines.call_args.args[0], "STOR LIT9028A")
        ftp.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
