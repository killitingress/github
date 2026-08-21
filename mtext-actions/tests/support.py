"""Gemeinsame Repository-Aufbauten für die Akzeptanztests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from lbs_delivery.config import Configuration, MANDANT_CONFIG_PATH, load_configuration

AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
ZERO_SHA = "0" * 40


class TempDirTestCase(unittest.TestCase):
    """Stellt für jeden Test ein frisches temporäres Verzeichnis bereit."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)


def git(repository: Path, *arguments: str) -> str:
    """Führt einen erwartbar erfolgreichen Git-Befehl aus."""

    result = subprocess.run(["git", "-C", str(repository), *arguments], check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout.strip()


def init_git_repository(repository: Path, *, branch: str | None = None) -> None:
    """Initialisiert ein Test-Repository mit lokaler Autorenkonfiguration."""

    if branch:
        git(repository, "init", "-b", branch)
    else:
        git(repository, "init", "-q")
    git(repository, "config", "user.name", "Test")
    git(repository, "config", "user.email", "test@example.invalid")


def jcl_template() -> str:
    """Liest die Mainframe-JCL-Vorlage aus dem CI/CD-Checkout."""

    return (AUTOMATION_ROOT / "templates/mainframe-upload.jcl").read_text(encoding="ascii")


def write_mandant(path: Path, **overrides: object) -> None:
    """Schreibt eine minimale FI-Mandantenkonfiguration."""

    mandant: dict[str, object] = {
        "kuerzel": "FI",
        "releaselinie": "270",
        "ispw": "P",
        "hostprofile": {
            "FKT": {"assignment": "LOMS000066", "stage": "FKTE"},
            "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
        },
    }
    mandant.update(overrides)
    path.write_text(json.dumps({"mandant": mandant}), encoding="utf-8")


def init_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein leeres Mandanten-Repository."""

    repository = root / "source"
    repository.mkdir()
    init_git_repository(repository, branch=branch)
    return repository


def track_remote_branch(repository: Path, branch: str) -> None:
    """Legt die von der Quellprüfung erwartete Remote-Branch-Referenz an."""

    git(repository, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")


def setup_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein Mandanten-Repository mit FI-Referenzprojekten."""

    repository = init_repository(root, branch=branch)
    for project_name in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_Basis", "LOMS_PKA"):
        project = repository / project_name
        project.mkdir()
        (project / "value.txt").write_text("content\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "init")
    return repository


def setup_sync_repository(root: Path) -> Path:
    """Erzeugt einen für die Synchronisation gültigen Entwicklungsstand."""

    repository = init_repository(root, branch="feature/261/test-sync")
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "value.txt").write_text("new", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "sync")
    track_remote_branch(repository, "feature/261/test-sync")
    return repository


def setup_release_repository(root: Path) -> Path:
    """Erzeugt eine Releasehistorie mit FULL-, Vorgänger- und DELTA-Tags."""

    repository = init_repository(root, branch="release/261")
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "baseline.txt").write_text("base\n", encoding="utf-8")
    (project / "deleted.txt").write_text("delete\n", encoding="utf-8")
    (project / "rename-old.txt").write_text("rename\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "full")
    git(repository, "tag", "r261.100")
    (project / "baseline.txt").write_text("changed\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "previous")
    git(repository, "tag", "r261.107")
    (project / "deleted.txt").unlink()
    (project / "new.txt").write_text("new\n", encoding="utf-8")
    git(repository, "mv", "LOMS_Basis/rename-old.txt", "LOMS_Basis/rename-new.txt")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "delta")
    git(repository, "tag", "r261.108")
    track_remote_branch(repository, "release/261")
    return repository


def load_test_configuration(
    repository: Path,
    *,
    mandant: dict[str, object] | None = None,
    repository_name: str = "FinanzInformatik/fi_lbs_entw_oms_fi",
) -> Configuration:
    """Schreibt lokale Mandantenangaben und lädt die produktive Konfiguration."""

    path = repository / MANDANT_CONFIG_PATH
    path.parent.mkdir(exist_ok=True)
    write_mandant(path, **(mandant or {}))
    return load_configuration(repository, repository_name)
