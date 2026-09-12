"""Lädt (und prüft) `.github/config.json` eines Mandanten-Repositories.

Die Angaben werden mit den Mandanten- und Releaselinienzuordnungen sowie den
vorhandenen Projektverzeichnissen abgeglichen. Das Ergebnis enthält alles, was
Paketbau, Synchronisierung und Übergabe aus der Konfiguration benötigen.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


# Stammverzeichnis dieses Repositories
ACTION_ROOT = Path(__file__).resolve().parents[2]

# Zuordnung vom Mandantenkürzel zum GitHub-Repository und Mainframe-Subsystem
MANDANTEN_ZUORDNUNG_PATH = ACTION_ROOT / "config/mandanten.json"

# Zuordnung von Releaselinien zu M/Text-Umgebungsarten
RELEASELINIEN_ZUORDNUNG_PATH = ACTION_ROOT / "config/releaselinien.json"

# Mapping von Dateiendungen zu technischen Formaten (z.B. ".model" => XML)
FILETYPE_MAPPINGS_PATH = ACTION_ROOT / "config/ressourcenformate.json"

# In dieses Verzeichnis wurde das Mandanten-Repository ausgecheckt
WORKFLOW_MANDANT_SOURCE = Path("source")

# Mandantenkonfiguration im ausgecheckten Mandanten-Repository
MANDANT_CONFIG_PATH = Path(".github/config.json")

# Dateiname des Vorbereitungs-Berichts
WORKFLOW_VORBEREITUNG_DATEI = Path("vorbereitung.json")

# Arten der M/Text-Umgebungen in `releaselinien.json`.
MTEXT_UMGEBUNG_ART_ENTWICKLUNG   = "Entwicklung"
MTEXT_UMGEBUNG_ART_FUNKTIONSTEST = "Funktionstest"

# Erlaubte CodePipeline-Umgebungen: `P` für Produktion und `T` für Test.
ISPW_INSTANZEN = {"T", "P"}

# Hostprofile dürfen auf diese CodePipeline-Stages verweisen
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}


@dataclass(frozen=True)
class Configuration:
    """Enthält die geprüften Angaben eines Mandanten-Repositories.

    `Configuration.load()` liest sie aus der Mandantenkonfiguration, den
    gemeinsamen Zuordnungen und den Projektverzeichnissen. Paketbau,
    Synchronisierung und Übergabe verwenden anschließend diese Angaben.
    """

    # Name des GitHub-Repositories
    repository: str
    # Mandantenkürzel
    kuerzel: str
    # Releaselinie, die `main` in diesem Repository bedeutet
    releaselinie: str
    # CodePipeline-Umgebung (Produktion oder Test)
    ispw: str
    # Dry Run baut alle Dateien, führt aber keine externe Übergabe aus
    dry_run: bool
    # Mainframe-Subsystem
    subsystem: str
    # Zuordnung der Projektverzeichnisse zu ihren Projektcodes (z.B. `LOMS_Basis[BY]` zu `BASIS`)
    projects: dict[str, str]
    # Projektverzeichnisse, die weder synchronisiert, geliefert noch als Ressource geprüft werden
    excluded_projects: tuple[str, ...]
    # Hostprofile mit CodePipeline-Stage und Assignment
    hostprofile: dict[str, dict[str, str]]
    # Zuordnung von Releaselinien zu M/Text-Umgebungsarten
    releaselinien: dict[str, dict[str, str]]
    # Präfix der M/Text-Umgebung je Umgebungsart
    mtext_umgebung_prefixe: dict[str, str]

    def excludes_project_path(self, relative_path: Path) -> bool:
        """Gibt Wahr zurück, wenn ein Pfad zu excluded_projects gehört."""

        return bool(relative_path.parts) and relative_path.parts[0] in self.excluded_projects

    @classmethod
    def load(cls, repository_root: Path, repository_name: str) -> Configuration:
        """Lädt und prüft die Konfiguration eines ausgecheckten Mandanten-Repositories."""

        mandant_configuration   = _read_json(repository_root / MANDANT_CONFIG_PATH)
        mandanten_zuordnung     = _read_json(MANDANTEN_ZUORDNUNG_PATH)
        releaselinien_zuordnung = _read_json(RELEASELINIEN_ZUORDNUNG_PATH)

        mtext_ziele   = releaselinien_zuordnung["mtext_ziele"]
        releaselinien = releaselinien_zuordnung["releaselinien"]

        repositories = [e["repository"] for e in mandanten_zuordnung.values()]
        if len(repositories) != len(set(repositories)): # jeder Mandant darf nur einmal definiert sein
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist nicht eindeutig")

        if set(mtext_ziele) != {MTEXT_UMGEBUNG_ART_ENTWICKLUNG, MTEXT_UMGEBUNG_ART_FUNKTIONSTEST}:
            raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Umgebungsarten sind ungültig: " + ", ".join(mtext_ziele))

        mandant = mandant_configuration["mandant"]

        if mandant["releaselinie"] not in releaselinien:
            raise DeliveryError(Status.VALIDATION_FAILED, f"führende Releaselinie #{mandant['releaselinie']} ist ungültig")

        stammdaten = mandanten_zuordnung.get(mandant["kuerzel"])
        if stammdaten is None or repository_name != stammdaten["repository"]:
            raise DeliveryError(Status.VALIDATION_FAILED, f"Mandant #{mandant['kuerzel']} passt nicht zum Repository")

        if mandant["ispw"] not in ISPW_INSTANZEN:
            raise DeliveryError(Status.VALIDATION_FAILED, f"ISPW-Instanz #{mandant['ispw']} ist ungültig")

        if not isinstance(mandant.get("dry_run", False), bool):
            raise DeliveryError(Status.VALIDATION_FAILED, "dry_run muss true oder false sein")

        for name, profile in mandant["hostprofile"].items():
            if profile["stage"] not in CODEPIPELINE_STAGES or not profile.get("assignment"):
                raise DeliveryError(Status.VALIDATION_FAILED, f"Hostprofil #{name} ist ungültig")

        # sichtbare Projektverzeichnisse in Projektcodes umwandeln
        projects: dict[str, str] = {}
        for item in sorted(repository_root.iterdir(), key=lambda path: path.name):
            if not item.is_dir() or item.name.startswith(".") or item.name in mandant.get("excluded_projects", []):
                continue
            projects[item.name] = item.name.removesuffix(f"[{mandant['kuerzel']}]").removeprefix("LOMS_")[:5].upper()

        if not projects or len(projects) != len(set(projects.values())):
            raise DeliveryError(Status.VALIDATION_FAILED, "abgeleitete Projektcodes sind nicht eindeutig")

        # prüfen, ob alle Hostprofile in der Mandantenkonfiguration definiert sind
        for linie, values in releaselinien.items():
            if values["hostprofil"] not in mandant["hostprofile"]:
                raise DeliveryError(Status.VALIDATION_FAILED, f"Releaselinie #{linie} ist ungültig")

        # wir erzeugen freundlicher Weise ein Objekt der Klasse Configuration, das alle relevanten Informationen enthält
        return cls(
            repository=repository_name,
            kuerzel=mandant["kuerzel"],
            releaselinie=mandant["releaselinie"],
            ispw=mandant["ispw"],
            dry_run=mandant.get("dry_run", False),
            subsystem=stammdaten["subsystem"],
            projects=projects,
            excluded_projects=tuple(mandant.get("excluded_projects", [])),
            hostprofile=mandant["hostprofile"],
            releaselinien=releaselinien,
            mtext_umgebung_prefixe=mtext_ziele,
        )


def _read_json(path: Path) -> Any:
    """Liest eine JSON-Konfigurationsdatei und gibt den geparsten Inhalt zurück."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Datei '{path.name}' kann nicht gelesen werden: {exc}"
        raise DeliveryError(Status.VALIDATION_FAILED, message) from exc


def mandant_source() -> Path:
    """Gibt den Pfad des im Workflow ausgecheckten Mandanten-Repositories zurück."""

    return Path(os.environ["GITHUB_WORKSPACE"]) / WORKFLOW_MANDANT_SOURCE
