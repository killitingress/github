"""Lädt und prüft `.github/config.json` eines Mandanten-Repositories.

Die Angaben werden mit den Mandanten- und Releaselinienzuordnungen sowie den
vorhandenen Projektverzeichnissen abgeglichen. Das Ergebnis enthält alles, was
Paketbau, Synchronisation und Übergabe aus der Konfiguration benötigen.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


# Wurzel des zentralen CI/CD-Checkouts mit den versionierten Zuordnungen für
# Mandanten und Releaselinien.
AUTOMATION_ROOT = Path(__file__).resolve().parents[2]

# Zuordnung vom Mandantenkürzel zum GitHub-Repository und Mainframe-Subsystem.
MANDANTEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/mandanten.json"

# Zuordnung der M/Text-Ziele und aktiven Releaselinien zu Präfixen,
# Zahlenteilen der ETAPS-Linien und Hostprofilen.
RELEASELINIEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/releaselinien.json"

# Mandantenkonfiguration im ausgecheckten Repository.
MANDANT_CONFIG_PATH = Path(".github/config.json")

# Fachliche Bezeichnungen der M/Text-Zielstufen in `releaselinien.json`.
MTEXT_ZIEL_ENTWICKLUNG = "Entwicklung"
MTEXT_ZIEL_FUNKTIONSTEST = "Funktionstest"

# Die Reihenfolge der M/Text-Ziele gilt beim vollständigen Abgleich nach einem
# Releaselinienwechsel. Dieselben Ziele müssen zentral konfiguriert sein.
MTEXT_ZIEL_REIHENFOLGE = (MTEXT_ZIEL_ENTWICKLUNG, MTEXT_ZIEL_FUNKTIONSTEST)

# Erlaubte CodePipeline-Umgebungen: `P` für Produktion und `T` für Test.
ISPW_INSTANZEN = {"T", "P"}

# Hostprofile dürfen auf diese sechs eingerichteten CodePipeline-Stages zeigen.
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}

# Erwartete Projektverzeichnisse je Mandant. Abweichungen werden als Warnung gemeldet.
_PROJEKTREFERENZ = {
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
    """Enthält die geprüften Angaben eines Mandanten-Repositories.

    `load_configuration()` liest sie aus der Mandantenkonfiguration, den
    zentralen Zuordnungen und den Projektverzeichnissen. Paketbau,
    Synchronisation und Übergabe verwenden anschließend diese Angaben.
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
    # Zuletzt über den Lieferbranch freigegebene Release-Version. Vor dem
    # ersten Release steht hier `None`.
    letztes_release: str | None
    # Mainframe-Subsystem
    subsystem: str
    # Zuordnung der Projektverzeichnisse zu ihren Projektcodes, zum Beispiel `LOMS_Basis[BY]` zu `BASIS`.
    projects: dict[str, str]
    # In `.github/config.json` benannte Hostprofile mit CodePipeline-Stage und Assignment.
    hostprofile: dict[str, dict[str, str]]
    # Zentrale Zuordnung aller aktiven Linien aus `releaselinien.json`. Die
    # Schlüssel sind Linien wie `270`, die Werte nennen den Zahlenteil der
    # ETAPS-Linie und das Hostprofil.
    releaselinien: dict[str, dict[str, str]]
    # Präfix der M/Text-Umgebung für Entwicklung und Funktionstest.
    mtext_ziel_prefixe: dict[str, str]
    # Warnungen zu fehlenden oder zusätzlichen Projektverzeichnissen.
    warnungen: tuple[str, ...]


@dataclass(frozen=True)
class MandantStamm:
    """Ordnet einem Mandantenkürzel Repository und Mainframe-Subsystem zu.

    Die Zuordnung verhindert, dass eine Datei im Repository das `kuerzel` oder
    Mainframe-Subsystem eines anderen Mandanten beansprucht.
    """

    repository: str
    subsystem: str


def release_branches(configuration: Configuration, releaselinie: str) -> tuple[str, ...]:
    """Gibt die zulässigen Lieferbranches einer Releaselinie zurück."""

    if configuration.releaselinie == releaselinie:
        return "main", f"release/{releaselinie}"
    return (f"release/{releaselinie}",)


def _read_json(path: str | Path) -> Any:
    """Liest eine JSON-Konfigurationsdatei und gibt den geparsten Inhalt zurück."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Konfiguration kann nicht gelesen werden: {Path(path).name}"
        raise DeliveryError(Status.VALIDATION_FAILED, message) from exc


def load_mandanten_zuordnung(path: str | Path) -> dict[str, MandantStamm]:
    """Lädt Repository und Mainframe-Subsystem je Mandantenkürzel."""

    mandanten = _read_json(path)
    zuordnung: dict[str, MandantStamm] = {}
    repositories: set[str] = set()

    # Jede Zuordnung braucht ein eindeutiges Repository und Subsystem.
    for kuerzel, values in mandanten.items():
        repository = values["repository"]
        subsystem = values["subsystem"]
        if repository in repositories:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist nicht eindeutig")
        repositories.add(repository)
        zuordnung[kuerzel] = MandantStamm(repository=repository, subsystem=subsystem)

    return zuordnung


def load_releaselinien_zuordnung(path: str | Path) -> tuple[dict[str, str], dict[str, Any]]:
    """Lädt M/Text-Ziele und aktive Releaselinien aus releaselinien.json."""

    document = _read_json(path)
    mtext_ziele = document["mtext_ziele"]
    if set(mtext_ziele) != set(MTEXT_ZIEL_REIHENFOLGE):
        raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Ziele sind ungültig")
    mtext_ziel_prefixe = {zielstufe: mtext_ziele[zielstufe] for zielstufe in MTEXT_ZIEL_REIHENFOLGE}
    return mtext_ziel_prefixe, document["releaselinien"]


def load_configuration(repository_root: str | Path, repository_name: str) -> Configuration:
    """Lädt und prüft die Konfiguration eines ausgecheckten Mandanten-Repositories."""

    root = Path(repository_root)

    # Zentrale Zuordnungen und Mandantenkonfiguration laden.
    mandant_configuration = _read_json(root / MANDANT_CONFIG_PATH)
    mandanten_zuordnung = load_mandanten_zuordnung(MANDANTEN_ZUORDNUNG_PATH)
    mtext_ziel_prefixe, releaselinien = load_releaselinien_zuordnung(
        RELEASELINIEN_ZUORDNUNG_PATH
    )

    mandant = mandant_configuration["mandant"]
    kuerzel = mandant["kuerzel"]
    releaselinie = mandant["releaselinie"]
    ispw = mandant["ispw"]
    letztes_release = mandant.get("letztes_release")
    hostprofile = mandant["hostprofile"]
    excluded_projects = mandant.get("excluded_projects", [])
    if not isinstance(excluded_projects, list):
        raise DeliveryError(Status.VALIDATION_FAILED, "ausgeschlossene Projekte sind ungültig")

    if releaselinie not in releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "führende Releaselinie ist ungültig")

    # Mandantenidentität und Hostprofile prüfen.
    mandant_stammdaten = mandanten_zuordnung.get(kuerzel)
    if mandant_stammdaten is None or repository_name != mandant_stammdaten.repository:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mandant passt nicht zum Repository")

    if ispw not in ISPW_INSTANZEN:
        raise DeliveryError(Status.VALIDATION_FAILED, "ISPW-Instanz ist ungültig")
    if letztes_release is not None and not isinstance(letztes_release, str):
        raise DeliveryError(Status.VALIDATION_FAILED, "letztes Release ist ungültig")

    for profile in hostprofile.values():
        if profile["stage"] not in CODEPIPELINE_STAGES or not profile.get("assignment"):
            raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofil ist ungültig")

    # Lieferbare Projekte ermitteln und Releaselinien abgleichen.
    projects = _scan_projects(root, kuerzel, tuple(excluded_projects))
    for values in releaselinien.values():
        if values["hostprofil"] not in hostprofile:
            raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist ungültig")

    return Configuration(
        repository=repository_name,
        kuerzel=kuerzel,
        releaselinie=releaselinie,
        ispw=ispw,
        letztes_release=letztes_release,
        subsystem=mandant_stammdaten.subsystem,
        projects=projects,
        hostprofile=hostprofile,
        releaselinien=releaselinien,
        mtext_ziel_prefixe=mtext_ziel_prefixe,
        warnungen=_reference_warnings(kuerzel, projects),
    )


def _scan_projects(root: Path, kuerzel: str, excluded_projects: tuple[str, ...]) -> dict[str, str]:
    """Ermittelt lieferbare Projekte und leitet ihre Projektcodes ab."""

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
    """Meldet fehlende und zusätzliche Projekte gegenüber der hinterlegten Liste."""

    referenz = _PROJEKTREFERENZ.get(kuerzel)
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


def run_validation(_arguments: argparse.Namespace) -> dict[str, object]:
    """Prüft die Mandantenkonfiguration des Workflow-Arbeitsbereichs."""

    source = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "source"
    configuration = load_configuration(source, os.environ["GITHUB_REPOSITORY"])
    return {
        "status": Status.CONFIG_VALIDATED.value,
        "mandanten_kuerzel": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": configuration.releaselinie,
        "releaselinien": sorted(configuration.releaselinien),
        "letztes_release": configuration.letztes_release,
    } | ({"warnungen": list(configuration.warnungen)} if configuration.warnungen else {})
