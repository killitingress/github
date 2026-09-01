"""Lädt (und prüft) `.github/config.json` eines Mandanten-Repositories.

Die Angaben werden mit den Mandanten- und Releaselinienzuordnungen sowie den
vorhandenen Projektverzeichnissen abgeglichen. Das Ergebnis enthält alles, was
Paketbau, Synchronisation und Übergabe aus der Konfiguration benötigen.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


# Stammverzeichnis dieses Repositories. Darunter liegen die gemeinsamen
# Konfigurationsdateien und Vorlagen.
AUTOMATION_ROOT = Path(__file__).resolve().parents[2]

# Zuordnung vom Mandantenkürzel zum GitHub-Repository und Mainframe-Subsystem.
MANDANTEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/mandanten.json"

# Zuordnung der M/Text-Umgebungsarten und aktiven Releaselinien zu Präfixen,
# Zahlenteilen der ETAPS-Linien und Hostprofilen.
RELEASELINIEN_ZUORDNUNG_PATH = AUTOMATION_ROOT / "config/releaselinien.json"

# Mandantenkonfiguration im ausgecheckten Repository.
MANDANT_CONFIG_PATH = Path(".github/config.json")

# Verzeichnis des ausgecheckten Mandanten-Repositories im GitHub-Workflow-Arbeitsbereich.
WORKFLOW_MANDANT_SOURCE = Path("source")

# Dateiname der Liefer-Vorbereitung im Arbeitsbereich und im Vorbereitungsverzeichnis.
WORKFLOW_VORBEREITUNG_DATEI = Path("vorbereitung.json")

# Zuordnung der zu prüfenden Ressourcenformate in mtext-actions.
RESOURCE_FORMATS_PATH = AUTOMATION_ROOT / "config/ressourcenformate.json"

# Arten der M/Text-Umgebungen in `releaselinien.json`.
MTEXT_UMGEBUNG_ART_ENTWICKLUNG = "Entwicklung"
MTEXT_UMGEBUNG_ART_FUNKTIONSTEST = "Funktionstest"

# Beide Umgebungsarten müssen in der gemeinsamen Zuordnung vorhanden sein.
MTEXT_UMGEBUNG_ARTEN = (MTEXT_UMGEBUNG_ART_ENTWICKLUNG, MTEXT_UMGEBUNG_ART_FUNKTIONSTEST)

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

    `Configuration.load()` liest sie aus der Mandantenkonfiguration, den
    gemeinsamen Zuordnungen und den Projektverzeichnissen. Paketbau,
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
    # Mainframe-Subsystem
    subsystem: str
    # Zuordnung der Projektverzeichnisse zu ihren Projektcodes, zum Beispiel `LOMS_Basis[BY]` zu `BASIS`.
    projects: dict[str, str]
    # In `.github/config.json` benannte Hostprofile mit CodePipeline-Stage und Assignment.
    hostprofile: dict[str, dict[str, str]]
    # Gemeinsame Zuordnung aller aktiven Linien aus `releaselinien.json`. Die
    # Schlüssel sind Linien wie `270`, die Werte nennen den Zahlenteil der
    # ETAPS-Linie und das Hostprofil.
    releaselinien: dict[str, dict[str, str]]
    # Präfix der M/Text-Umgebung je Umgebungsart.
    mtext_umgebung_prefixe: dict[str, str]
    # Warnungen zu fehlenden oder zusätzlichen Projektverzeichnissen.
    warnungen: tuple[str, ...]

    def release_branches(self, releaselinie: str) -> tuple[str, ...]:
        """Gibt die zulässigen Lieferbranches einer Releaselinie zurück."""

        if self.releaselinie == releaselinie:
            return "main", f"release/{releaselinie}"

        return (f"release/{releaselinie}",)

    @classmethod
    def load_releaselinien_zuordnung(cls, path: str | Path) -> tuple[dict[str, str], dict[str, Any]]:
        """Lädt M/Text-Umgebungsarten und aktive Releaselinien."""

        document = _read_json(path)
        umgebung_arten = document["mtext_ziele"]

        if set(umgebung_arten) != set(MTEXT_UMGEBUNG_ARTEN):
            raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Umgebungsarten sind ungültig")

        mtext_umgebung_prefixe = {e: umgebung_arten[e] for e in MTEXT_UMGEBUNG_ARTEN}
        return mtext_umgebung_prefixe, document["releaselinien"]

    @classmethod
    def load_mandanten_zuordnung(cls, path: str | Path) -> dict[str, dict[str, str]]:
        """Lädt Repository und Mainframe-Subsystem je Mandantenkürzel aus mandanten.json."""

        mandanten = _read_json(path)
        zuordnung: dict[str, dict[str, str]] = {}
        repositories: set[str] = set()

        # Jedes Mandantenkürzel braucht ein eindeutiges Repository.
        for kuerzel, values in mandanten.items():
            repository = values["repository"]
            subsystem = values["subsystem"]

            if repository in repositories:
                raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist nicht eindeutig")

            repositories.add(repository)
            zuordnung[kuerzel] = {"repository": repository, "subsystem": subsystem}

        return zuordnung

    @classmethod
    def load(cls, repository_root: str | Path, repository_name: str) -> Configuration:
        """Lädt und prüft die Konfiguration eines ausgecheckten Mandanten-Repositories."""

        root = Path(repository_root)

        # Gemeinsame Zuordnungen und Mandantenkonfiguration laden.
        mandant_configuration = _read_json(root / MANDANT_CONFIG_PATH)
        mandanten_zuordnung = cls.load_mandanten_zuordnung(MANDANTEN_ZUORDNUNG_PATH)
        mtext_umgebung_prefixe, releaselinien = cls.load_releaselinien_zuordnung(RELEASELINIEN_ZUORDNUNG_PATH)

        mandant = mandant_configuration["mandant"]
        kuerzel = mandant["kuerzel"]
        releaselinie = mandant["releaselinie"]
        ispw = mandant["ispw"]
        hostprofile = mandant["hostprofile"]
        excluded_projects = mandant.get("excluded_projects", [])
        if not isinstance(excluded_projects, list):
            raise DeliveryError(Status.VALIDATION_FAILED, "ausgeschlossene Projekte sind ungültig")

        if releaselinie not in releaselinien:
            raise DeliveryError(Status.VALIDATION_FAILED, "führende Releaselinie ist ungültig")

        # Mandantenidentität und Hostprofile prüfen.
        stammdaten = mandanten_zuordnung.get(kuerzel)
        if stammdaten is None or repository_name != stammdaten["repository"]:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandant passt nicht zum Repository")

        if ispw not in ISPW_INSTANZEN:
            raise DeliveryError(Status.VALIDATION_FAILED, "ISPW-Instanz ist ungültig")

        for profile in hostprofile.values():
            if profile["stage"] not in CODEPIPELINE_STAGES or not profile.get("assignment"):
                raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofil ist ungültig")

        # Lieferbare Projekte ermitteln und Releaselinien abgleichen.
        projects = _scan_projects(root, kuerzel, tuple(excluded_projects))
        for values in releaselinien.values():
            if values["hostprofil"] not in hostprofile:
                raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist ungültig")

        return cls(
            repository=repository_name,
            kuerzel=kuerzel,
            releaselinie=releaselinie,
            ispw=ispw,
            subsystem=stammdaten["subsystem"],
            projects=projects,
            hostprofile=hostprofile,
            releaselinien=releaselinien,
            mtext_umgebung_prefixe=mtext_umgebung_prefixe,
            warnungen=_reference_warnings(kuerzel, projects),
        )


def _read_json(path: str | Path) -> Any:
    """Liest eine JSON-Konfigurationsdatei und gibt den geparsten Inhalt zurück."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Konfiguration kann nicht gelesen werden: {Path(path).name}: {exc}"
        raise DeliveryError(Status.VALIDATION_FAILED, message) from exc


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
    warnings: list[str] = []

    missing = sorted(referenz - names)
    if missing:
        warnings.append("Projekte fehlen gegenüber dem aktuellen Referenzstand: " + ", ".join(missing))

    additional = sorted(names - referenz)

    if additional:
        warnings.append("Projekte sind gegenüber dem aktuellen Referenzstand zusätzlich: " + ", ".join(additional))

    return tuple(warnings)


def workflow_workspace() -> Path:
    """Gibt den Arbeitsbereich des aktuellen GitHub-Actions-Laufs zurück."""

    return Path(os.environ.get("GITHUB_WORKSPACE", "."))


def mandant_source() -> Path:
    """Gibt den Pfad des im Workflow ausgecheckten Mandanten-Repositories zurück."""

    return workflow_workspace() / WORKFLOW_MANDANT_SOURCE


def run() -> dict[str, object]:
    """Prüft die Mandantenkonfiguration des Workflow-Arbeitsbereichs."""

    configuration = Configuration.load(mandant_source(), os.environ["GITHUB_REPOSITORY"])
    return {
        "status": Status.CONFIG_VALIDATED.value,
        "mandanten_kuerzel": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": configuration.releaselinie,
        "releaselinien": sorted(configuration.releaselinien),
    } | ({"warnungen": list(configuration.warnungen)} if configuration.warnungen else {})
