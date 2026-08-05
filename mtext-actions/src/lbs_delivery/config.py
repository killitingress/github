"""Zentrale Validierung von .github/config.json der Mandanten.

Das Modul verbindet die Mandanten- und Releaselinienzuordnungen
mit der Konfiguration und den Projektverzeichnissen des ausgecheckten
Repositories. Alle späteren Lieferschritte erhalten so ein geprüftes,
unveränderliches Eingabemodell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


# Pfad des Automation-Root-Verzeichnisses (darin suchen wir die
# Konfigurationsdateien für Mandanten und Releaselinien)
AUTOMATION_ROOT = Path(__file__).resolve().parents[2]
# Zuordnung vom Mandantenkürzel zum GitHub-Repository und Mainframe-Subsystem.
MANDANTEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/mandanten.json"
# Zuordnung der aktiven Releaselinien zu ETAPS-Linien und Hostprofilen.
RELEASELINIEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/releaselinien.json"
# Mandantenkonfiguration im ausgecheckten Repository.
MANDANT_CONFIG_PATH = Path(".github/config.json")

# CodePipeline-Umgebung - "P" = Produktion, "T" = Testumgebung
ISPW_INSTANZEN = {"T", "P"}

# Hostprofile dürfen auf diese sechs eingerichteten CodePipeline-Stages zeigen.
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}

# Referenz-Projektbestand je Mandant, für Warnungen bei Abweichungen
PROJEKTREFERENZ = {
    "FI": {"Configuration", "Fonts", "LOMS_Framework", "LOMS_Basis", "LOMS_PKA"},
    "IT": {"LOMS_Autonom"},
    "BY": {"LOMS_Basis[BY]", "LOMS_Autonom[BY]"},
    "LH": {"LOMS_Basis[LH]", "LOMS_Autonom[LH]"},
    "NW": {"LOMS_Basis[NW]", "LOMS_Autonom[NW]"},
    "OS": {"LOMS_Basis[OS]", "LOMS_Autonom[OS]"},
    "SA": {"LOMS_Basis[SA]", "LOMS_Autonom[SA]"},
}


@dataclass(frozen=True)
class Configuration:
    """Enthält die geprüften Eingaben, die alle Workflows gemeinsam verwenden.

    Die Konfiguration wird einmal an der Workflow-Grenze aufgebaut. Paketbau,
    Synchronisation und Übergabe müssen die Repositorydaten dadurch nicht
    neu ermitteln. Wird von load_configuration() zurückgegeben.
    """

    # Name des GitHub-Repositories
    repository: str
    # Mandantenkürzel
    kuerzel: str
    # Releaselinie, die `main` in diesem Repository führt. Steht in
    # `.github/config.json` und gilt für Sync und Release auf `main`, wenn der
    # Branchname keine Linie enthält.
    releaselinie: str
    # CodePipeline-Umgebung (Produktion oder Testumgebung)
    ispw: str
    # Mainframe-Subsystem
    subsystem: str
    # Dictionary von Projektnamen zu Projektcodes (Beispiel: LOMS_Basis[BY] -> BASIS)
    projects: dict[str, str]
    # Dictionary von Hostprofilen zu Hostprofilen 
    hostprofile: dict[str, dict[str, str]]
    # Zentrale Zuordnung aller aktiven Linien aus `releaselinien.json`. Die
    # Schlüssel sind Linien wie `R270`, die Werte nennen ETAPS-Linie und
    # Hostprofil.
    releaselinien: dict[str, dict[str, str]]
    # Tuple von Warnungen bei Abweichungen vom Referenzbestand
    warnungen: tuple[str, ...]


@dataclass(frozen=True)
class MandantStamm:
    """Beschreibt die zentrale Identität eines Mandanten-Repositories.

    Die Zuordnung verhindert, dass eine Datei im Repository das `kuerzel` oder
    Mainframe-Subsystem eines anderen Mandanten beansprucht.
    """

    repository: str
    subsystem: str


def _read_json(path: str | Path) -> Any:
    """Liest eine JSON-Konfigurationsdatei und gibt den geparsten Inhalt zurück."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Konfiguration kann nicht gelesen werden: {Path(path).name}"
        raise DeliveryError(Status.VALIDATION_FAILED, message) from exc


def _load_mandanten_zuordnung(path: str | Path) -> dict[str, MandantStamm]:
    """Lädt die Zuordnung des `kuerzel`s zur Repositoryidentität aus
    mandanten.json."""

    mandanten = _read_json(path)
    if not isinstance(mandanten, dict) or not mandanten:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")

    zuordnung: dict[str, MandantStamm] = {}
    repositories: set[str] = set() # Set für Eindeutigkeit

    # Jede Zuordnung braucht eindeutiges Repository und Subsystem.
    for kuerzel, values in mandanten.items():
        if not isinstance(kuerzel, str) or not kuerzel:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")
        if not isinstance(values, dict):
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")
        try:
            repository = values["repository"]
            subsystem = values["subsystem"]
        except KeyError as exc:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig") from exc

        if not isinstance(repository, str) or not repository or not isinstance(subsystem, str) or not subsystem:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")

        if repository in repositories:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist nicht eindeutig")
        
        # Gültiges Repository und Subsystem hinzufügen
        repositories.add(repository)
        zuordnung[kuerzel] = MandantStamm(repository=repository, subsystem=subsystem)

    return zuordnung


def _load_releaselinien_zuordnung(path: str | Path) -> dict[str, Any]:
    """Lädt die Zuordnung der aktiven Releaselinien aus releaselinien.json."""

    releaselinien = _read_json(path)
    if not isinstance(releaselinien, dict) or not releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinien fehlen")
    return releaselinien


def load_configuration(repository_root: str | Path, repository_name: str) -> Configuration:
    """Hauptmethode - lädt die Konfiguration für ein ausgechecktes
    Mandanten-Repository. Wird auch von validate_config.py verwendet.
    """

    root = Path(repository_root)

    # Zentrale Zuordnungen und Mandantenkonfiguration laden.
    mandant_configuration = _read_json(root / MANDANT_CONFIG_PATH)
    mandanten_zuordnung = _load_mandanten_zuordnung(MANDANTEN_ZUORDNUNG_PATH)
    releaselinien = _load_releaselinien_zuordnung(RELEASELINIEN_ZUORDNUNG_PATH)

    try:
        mandant = mandant_configuration["mandant"]
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig") from exc
    if not isinstance(mandant, dict):
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig")

    try:
        kuerzel = mandant["kuerzel"]
        releaselinie = mandant["releaselinie"]
        ispw = mandant["ispw"]
        hostprofile = mandant["hostprofile"]
        excluded_projects = mandant.get("excluded_projects", [])
    except KeyError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig") from exc

    if not isinstance(kuerzel, str) or not kuerzel:
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig")
    if releaselinie not in releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "führende Releaselinie ist ungültig")
    if not isinstance(excluded_projects, list) or not all(isinstance(item, str) for item in excluded_projects):
        raise DeliveryError(Status.VALIDATION_FAILED, "ausgeschlossene Projekte sind ungültig")

    # Mandantenidentität und Hostprofile prüfen.
    mandant_stammdaten = mandanten_zuordnung.get(kuerzel)
    if mandant_stammdaten is None or repository_name != mandant_stammdaten.repository:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mandant passt nicht zum Repository")

    if ispw not in ISPW_INSTANZEN:
        raise DeliveryError(Status.VALIDATION_FAILED, "ISPW-Instanz ist ungültig")

    if not isinstance(hostprofile, dict) or not hostprofile:
        raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofile fehlen")

    for profile in hostprofile.values():
        if not isinstance(profile, dict):
            raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofil ist ungültig")
        if profile.get("stage") not in CODEPIPELINE_STAGES or not profile.get("assignment"):
            raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofil ist ungültig")

    # Lieferbare Projekte ermitteln und Releaselinien abgleichen.
    projects = _scan_projects(root, kuerzel, tuple(excluded_projects))
    for values in releaselinien.values():
        if not isinstance(values, dict):
            raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist ungültig")
        etaps_linie = values.get("etaps_linie")
        hostprofil = values.get("hostprofil")
        if not isinstance(etaps_linie, str) or not etaps_linie or hostprofil not in hostprofile:
            raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist ungültig")

    # Konfiguration zurückgeben
    return Configuration(
        repository=repository_name,
        kuerzel=kuerzel,
        releaselinie=releaselinie,
        ispw=ispw,
        subsystem=mandant_stammdaten.subsystem,
        projects=projects,
        hostprofile=hostprofile,
        releaselinien=releaselinien,
        warnungen=_reference_warnings(kuerzel, projects),
    )


def _scan_projects(root: Path, kuerzel: str, excluded_projects: tuple[str, ...]) -> dict[str, str]:
    """Ermittelt lieferbare Projekte und leitet deren "Projektcodes" ab.
    (Beispiel: LOMS_Basis[BY] -> BASIS)
    """

    projects: dict[str, str] = {}
    for item in sorted(root.iterdir(), key=lambda path: path.name):
        # Ausgeschlossene und versteckte Verzeichnisse entfallen vor der Pfadprüfung
        if not item.is_dir() or item.name.startswith(".") or item.name in excluded_projects:
            continue
        projects[item.name] = item.name.removesuffix(f"[{kuerzel}]").removeprefix("LOMS_")[:5].upper()

    if not projects or len(projects) != len(set(projects.values())):
        raise DeliveryError(Status.VALIDATION_FAILED, "abgeleitete Projektcodes sind nicht eindeutig")

    return projects


def _reference_warnings(kuerzel: str, projects: dict[str, str]) -> tuple[str, ...]:
    """Vergleicht die gefundenen Projekte mit dem unverbindlichen Referenzbestand."""

    referenz = PROJEKTREFERENZ.get(kuerzel)
    if referenz is None:
        return (f"Mandant besitzt keinen aktuellen Projekt-Referenzstand: {kuerzel}",)

    names = set(projects)
    warnungen: list[str] = []

    fehlend = sorted(referenz - names)
    if fehlend:
        warnungen.append("Projekte fehlen gegenüber dem aktuellen Referenzstand: " + ", ".join(fehlend))

    zusaetzlich = sorted(names - referenz)
    if zusaetzlich:
        warnungen.append("Projekte sind gegenüber dem aktuellen Referenzstand zusätzlich: " + ", ".join(zusaetzlich))

    return tuple(warnungen)
