"""Stellt gemeinsame Repository-Testaufbauten für die Akzeptanztests bereit.

Die Funktionen erzeugen kleine echte Git-Historien und Konfigurationsdateien.
Die Tests prüfen damit die produktiven Grenzen ohne Abhängigkeit von externen
Systemen.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lbs_delivery.config import Configuration, MANDANT_CONFIG_PATH, load_configuration


# Die Tests lesen zentrale Zuordnungen, Vorlagen und Workflows aus demselben
# Automations-Checkout wie die produktiven Module.
AUTOMATION_ROOT = Path(__file__).resolve().parents[1]


def git(repository: Path, *arguments: str) -> str:
    """Führt einen erwartbar erfolgreichen Git-Befehl in einem Test-Repository aus.

    Die bereinigte Standardausgabe hält den Testaufbau knapp. Mit `check=True`
    scheitert eine ungültige Testhistorie unmittelbar bei ihrer Erzeugung.
    """

    result = subprocess.run(["git", "-C", str(repository), *arguments], check=True, stdout=subprocess.PIPE, text=True)
    return result.stdout.strip()


def write_mandant(path: Path, **overrides: object) -> None:
    """Schreibt die kleinste repräsentative Mandantenkonfiguration der FI.

    Einzelne Tests überschreiben Felder in derselben JSON-Struktur wie die
    produktive Verarbeitung. Ungültige Varianten benötigen dadurch keine Kopie
    der vollständigen Ausgangskonfiguration.
    """

    mandant: dict[str, object] = {
        "kuerzel": "FI",
        "ispw": "P",
        "hostprofile": {
            "FKT": {"assignment": "LOMS000066", "stage": "FKTE"},
            "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
        },
    }
    mandant.update(overrides)
    path.write_text(json.dumps({"mandant": mandant}), encoding="utf-8")


def init_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein leeres Mandanten-Repository für reproduzierbare Test-Commits.

    Lokale Autorenangaben lösen den Testaufbau von der globalen Git-Konfiguration
    eines Entwicklers oder CI-Runners.
    """

    repository = root / "source"
    repository.mkdir()
    git(repository, "init", "-b", branch)
    git(repository, "config", "user.name", "Test")
    git(repository, "config", "user.email", "test@example.invalid")
    return repository


def track_remote_branch(repository: Path, branch: str) -> None:
    """Erzeugt die von der Quellprüfung erwartete Remote-Branch-Referenz.

    Die Tests benötigen kein echtes Remote-Repository. Die produktive
    Abstammungsprüfung verlangt jedoch gezielt die von GitHub Actions verwendete
    `origin`-Referenz.
    """

    git(repository, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")


def setup_repository(root: Path, *, branch: str) -> Path:
    """Erzeugt ein Mandanten-Repository mit festgeschriebenem FI-Referenzbestand.

    Es bildet den gültigen Ausgangspunkt der Konfigurationstests. Jeder Test kann
    darauf eine einzelne gezielte Abweichung einführen.
    """

    repository = init_repository(root, branch=branch)
    for project_name in ("Configuration", "Fonts", "LOMS_Framework", "LOMS_Basis", "LOMS_PKA"):
        project = repository / project_name
        project.mkdir()
        (project / "value.txt").write_text("content\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "init")
    return repository


def setup_sync_repository(root: Path) -> Path:
    """Erzeugt einen von der Synchronisationsprüfung akzeptierten Entwicklungsstand.

    Der Aufbau enthält ein Projekt und einen passenden Remote-Branch. Die Tests
    können sich dadurch auf Staging, Veröffentlichung und Adapterverhalten
    konzentrieren.
    """

    repository = init_repository(root, branch="R261/Entwicklung")
    project = repository / "LOMS_Basis"
    project.mkdir()
    (project / "value.txt").write_text("new", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "sync")
    track_remote_branch(repository, "R261/Entwicklung")
    return repository


def setup_release_repository(root: Path) -> Path:
    """Erzeugt eine Releasehistorie mit FULL-, Vorgänger- und DELTA-Tags.

    Hinzugefügte, geänderte, gelöschte und umbenannte Pfade liefern genügend
    Historie für die Prüfung von Archivbau und lesbarem Lieferbeleg.
    """

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
    git(repository, "mv", "LOMS_Basis/rename-old.txt", "LOMS_Basis/rename-new.txt")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "delta")
    git(repository, "tag", "R261.108")
    track_remote_branch(repository, "R261/Bereitstellung")
    return repository


def load_test_configuration(
    repository: Path, *, mandant: dict[str, object] | None = None, repository_name: str = "<oms_team>/mtext-fi",
) -> Configuration:
    """Schreibt lokale Mandantenangaben und lädt die produktive Konfiguration.

    Die Tests erhalten dasselbe unveränderliche Modell wie die echten Workflows.
    Darin enthalten sind auch die zentralen Mandanten- und
    Releaselinienzuordnungen aus dem Automations-Checkout.
    """

    path = repository / MANDANT_CONFIG_PATH
    path.parent.mkdir(exist_ok=True)
    write_mandant(path, **(mandant or {}))
    return load_configuration(repository, repository_name)
