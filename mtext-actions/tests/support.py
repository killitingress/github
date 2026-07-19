"""Stellt kleine gemeinsame Testeingaben bereit."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lbs_delivery.config import Configuration, load_configuration


# Diese Wurzel enthält Releaselinien, Templates und Workflow-Dateien der Automation.
AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
# Die produktionsnahe Releaselinienzuordnung gehört zum Testvertrag.
RELEASELINIEN = AUTOMATION_ROOT / "config/releaselinien.json"


def git(repository: Path, *arguments: str) -> str:
    """Führt Git in einem temporären Test-Repository aus."""

    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def write_mandant(path: Path, **overrides: object) -> None:
    """Schreibt die kleinste produktionsnahe Konfiguration der FI."""

    mandant: dict[str, object] = {
        "kuerzel": "FI",
        "repository": "mtext-fi",
        "ispw": "P",
        "subsystem": "LOMS",
        "hostprofile": {
            "FKT": {"assignment": "LOMS000066", "stage": "FKTE"},
            "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
        },
    }
    mandant.update(overrides)
    path.write_text(json.dumps({"mandant": mandant}), encoding="utf-8")


def init_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein leeres Mandanten-Repository mit Git-Benutzer."""

    repository = root / "mtext-fi"
    repository.mkdir()
    git(repository, "init", "-b", branch)
    git(repository, "config", "user.name", "Test")
    git(repository, "config", "user.email", "test@example.invalid")
    return repository


def track_remote_branch(repository: Path, branch: str) -> None:
    """Legt die vom Workflow erwartete Remote-Branch-Referenz an."""

    git(repository, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")


def setup_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein Mandanten-Repository mit einem gültigen Basisprojekt."""

    repository = init_repository(root, branch=branch)
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "value.txt").write_text("content\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "init")
    return repository


def setup_sync_repository(root: Path) -> Path:
    """Erzeugt einen erreichbaren Entwicklungscommit für Sync-Tests."""

    repository = init_repository(root, branch="R261/Entwicklung")
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "value.txt").write_text("new", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "sync")
    track_remote_branch(repository, "R261/Entwicklung")
    return repository


def setup_release_repository(root: Path) -> Path:
    """Erzeugt FULL-, Vorgänger- und DELTA-Tags für Release-Tests."""

    repository = init_repository(root, branch="R261/Bereitstellung")
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "baseline.txt").write_text("base\n", encoding="utf-8")
    (project / "deleted.txt").write_text("delete\n", encoding="utf-8")
    (project / "rename-old.txt").write_text("rename\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "full")
    git(repository, "tag", "R261.100")
    (project / "baseline.txt").write_text("changed\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "previous")
    git(repository, "tag", "R261.107")
    (project / "deleted.txt").unlink()
    (project / "new.txt").write_text("new\n", encoding="utf-8")
    git(
        repository,
        "mv",
        "LOMS_Basis/rename-old.txt",
        "LOMS_Basis/rename-new.txt",
    )
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "delta")
    git(repository, "tag", "R261.108")
    track_remote_branch(repository, "R261/Bereitstellung")
    return repository


def load_test_configuration(
    root: Path,
    repository: Path,
    *,
    mandant_path: Path | None = None,
    releaselinien_path: Path | None = None,
    mandant: dict[str, object] | None = None,
) -> Configuration:
    """Schreibt die Mandantenkonfiguration und lädt den Testvertrag."""

    path = mandant_path or root / "mandant.json"
    write_mandant(path, **(mandant or {}))
    return load_configuration(
        path,
        releaselinien_path or RELEASELINIEN,
        repository_name="mtext-fi",
        repository_root=repository,
    )
