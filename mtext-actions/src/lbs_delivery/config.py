"""Lädt die Mandantenkonfiguration und kennt die festen Lieferziele."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict, cast

from .delivery_names import project_code_for_name
from .errors import DeliveryError, Status
from .jcl import JCL_LEVELS, SUBSYSTEM_RE


# Grundform der eingelesenen JSON-Objekte vor der fachlichen Validierung.
JsonObject = dict[str, Any]


class HostprofilConfig(TypedDict):
    """Beschreibt die JCL-Zuordnung eines Hostprofils."""

    assignment: str
    stage: str


class MandantConfig(TypedDict):
    """Beschreibt die nach der Validierung verfügbare Mandantenkonfiguration."""

    kuerzel: str
    repository: str
    subsystem: str
    projects: list[str]
    hostprofile: dict[str, HostprofilConfig]


class ReleaselinieConfig(TypedDict):
    """Verknüpft eine Releaselinie mit M/Text-Linie und Übergabeprofil."""

    mtext_linie: str
    uebergabeprofil: str


# Versionierte Zuordnung der Releaselinien zu M/Text-Linie und Übergabeprofil.
Releaselinien = dict[str, ReleaselinieConfig]

# Reguläre Ausdrücke für die manuell geprüften Konfigurationswerte.
# Prüft die verbindliche Schreibweise einer Releaselinie, zum Beispiel `R261`.
RELEASELINIE_RE = re.compile(r"R[0-9]{3}")
# Prüft einen vollständigen Release-Tag, zum Beispiel `R261.108`.
RELEASE_TAG_RE = re.compile(r"R([0-9]{3})\.([0-9]{3})")
# Prüft den Namen eines Mandanten-Repositorys.
_REPOSITORY_RE = re.compile(r"mtext-(?:[a-z]{2}|autonom)")
# Prüft die erlaubten Zeichen und die maximale Länge eines Projektnamens.
_PROJECT_NAME_RE = re.compile(r"[A-Za-z0-9_\[\]-]{1,128}")
# Zulässige Kürzel der vorhandenen Mandanten-Repositorys.
MANDANTEN_KUERZEL = {"FI", "BY", "LH", "NW", "OS", "SA", "IT"}
# Ordnet der fachlichen Stage den serverSync- und Host-Suffix zu.
SYNC_STAGES = {"Entwicklung": ("E", "e"), "Abnahme": ("A", "a")}
# Unveränderlicher Payload des bestehenden M/Text-Adaptervertrags.
ADAPTER_PAYLOAD = {"mandant": "MAN", "institut": "INR"}


def _invalid(subject: str) -> None:
    """Bricht eine Konfigurationsprüfung mit stabilem Status ab."""

    raise DeliveryError(Status.VALIDATION_FAILED, f"ungültig: {subject}")


def _object(value: Any, keys: set[str], subject: str) -> JsonObject:
    """Prüft die vollständige Struktur eines Konfigurationsobjekts."""

    if not isinstance(value, dict) or set(value) != keys:
        _invalid(subject)
    return value


def _matches(value: Any, pattern: re.Pattern[str], subject: str) -> str:
    """Prüft ein formatiertes Pflichtfeld der Konfiguration."""

    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _invalid(subject)
    return value


def load_document(path: str | Path) -> JsonObject:
    """Liest ein JSON-Objekt."""

    config_path = Path(path)
    try:
        document = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"Konfiguration kann nicht gelesen werden: {config_path.name}",
        ) from exc
    if not isinstance(document, dict):
        _invalid("Konfiguration")
    return document


def load_mandant_config(
    config_path: str | Path, *, repository_name: str, repository_root: str | Path
) -> MandantConfig:
    """Lädt die Lieferkonfiguration und ermittelt Projekte aus der Repositorywurzel."""

    document = load_document(config_path)
    _object(document, {"mandant"}, "Mandantenkonfiguration")
    mandant = document["mandant"]
    required_fields = {"kuerzel", "repository", "subsystem", "hostprofile"}
    allowed_fields = required_fields | {"excluded_projects"}
    if (
        not isinstance(mandant, dict)
        or not required_fields.issubset(mandant)
        or not set(mandant).issubset(allowed_fields)
    ):
        _invalid("Mandant")
    if (
        not isinstance(mandant["kuerzel"], str)
        or mandant["kuerzel"] not in MANDANTEN_KUERZEL
    ):
        _invalid("Mandanten-Kürzel")
    _matches(mandant["repository"], _REPOSITORY_RE, "Mandanten-Repository")
    _matches(mandant["subsystem"], SUBSYSTEM_RE, "Mandanten-Subsystem")
    # Eine gültige Datei eines anderen Repositorys darf hier nicht verwendet werden.
    if mandant["repository"] != repository_name:
        _invalid("Repository-Zuordnung des Mandanten")

    excluded_projects = mandant.get("excluded_projects", [])
    if not isinstance(excluded_projects, list):
        _invalid("ausgeschlossene Projekte")
    for project in excluded_projects:
        _matches(project, _PROJECT_NAME_RE, "ausgeschlossener Projektname")
    if len(excluded_projects) != len(set(excluded_projects)):
        _invalid("doppelte ausgeschlossene Projekte")

    # Nur sichtbare Verzeichnisse direkt unter der Wurzel bilden M/Text-Projekte.
    root = Path(repository_root)
    try:
        projects = sorted(
            item.name
            for item in root.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and item.name not in excluded_projects
        )
    except OSError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "Repositorywurzel kann nicht gelesen werden",
        ) from exc
    if not projects:
        _invalid("Projekte des Mandanten")
    for project in projects:
        _matches(project, _PROJECT_NAME_RE, "Projektname")
    project_codes = [project_code_for_name(project) for project in projects]
    # Zwei Projekte dürfen nicht auf denselben historischen Liefercode abbilden.
    if len(project_codes) != len(set(project_codes)):
        _invalid("doppelte Zuordnung eines Liefercodes")

    hostprofile = mandant["hostprofile"]
    if not isinstance(hostprofile, dict) or not hostprofile:
        _invalid("Hostprofile")
    for hostprofil in hostprofile.values():
        hostprofil = _object(hostprofil, {"assignment", "stage"}, "Hostprofil")
        # Für Hostprofile gilt ausschließlich die Allowlist der
        # CodePipeline-Stages.
        if (
            not isinstance(hostprofil["stage"], str)
            or hostprofil["stage"] not in JCL_LEVELS
        ):
            _invalid("CodePipeline-Stage")
    return cast(
        MandantConfig,
        {
            "kuerzel": mandant["kuerzel"],
            "repository": mandant["repository"],
            "subsystem": mandant["subsystem"],
            "projects": projects,
            "hostprofile": hostprofile,
        },
    )


def load_releaselinien(path: str | Path) -> Releaselinien:
    """Lädt die kleine Zuordnung fachlicher zu technischen Linien."""

    document = load_document(path)
    if not document:
        _invalid("Releaselinien")
    for name, releaselinie in document.items():
        _matches(name, RELEASELINIE_RE, "Releaselinie")
        # Die versionierte Zuordnung selbst legt M/Text-Linie und Profilname fest.
        releaselinie = _object(
            releaselinie, {"mtext_linie", "uebergabeprofil"}, "Releaselinie"
        )
        for field in ("mtext_linie", "uebergabeprofil"):
            if not isinstance(releaselinie[field], str):
                _invalid(f"Feld {field} der Releaselinie")
    return cast(Releaselinien, document)


def validate_releaselinie(
    releaselinien: Releaselinien, releaselinie: str
) -> None:
    """Akzeptiert ausschließlich eine konfigurierte Releaselinie."""

    if releaselinie not in releaselinien:
        _invalid("Releaselinie")
