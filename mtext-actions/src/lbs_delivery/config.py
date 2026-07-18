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


class ProjectConfig(TypedDict):
    """Beschreibt ein fachliches Projekt und seinen Repositorypfad."""

    name: str
    source_path: str


class UebergabeprofilConfig(TypedDict):
    """Beschreibt die JCL-Zuordnung eines Übergabeprofils."""

    assignment: str
    stage: str


class MandantConfig(TypedDict):
    """Beschreibt die nach der Validierung verfügbare Mandantenkonfiguration."""

    kuerzel: str
    repository: str
    subsystem: str
    projects: list[ProjectConfig]
    uebergabeprofile: dict[str, UebergabeprofilConfig]


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
# Verhindert absolute Pfade, Nullbytes und Traversal in konfigurierten Quellpfaden.
_SOURCE_PATH_RE = re.compile(r"(?!/)(?!.*(?:^|/)\.\.(?:/|$))[^\x00]{1,256}")

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
    config_path: str | Path, *, repository_name: str
) -> MandantConfig:
    """Lädt und prüft die einzige variable Lieferkonfiguration."""

    document = load_document(config_path)
    _object(document, {"mandant"}, "Mandantenkonfiguration")
    mandant = _object(
        document["mandant"],
        {"kuerzel", "repository", "subsystem", "projects", "uebergabeprofile"},
        "Mandant",
    )
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

    projects = mandant["projects"]
    if not isinstance(projects, list) or not projects:
        _invalid("Projekte des Mandanten")
    for project in projects:
        project = _object(project, {"name", "source_path"}, "Projekt")
        _matches(project["name"], _PROJECT_NAME_RE, "Projektname")
        _matches(project["source_path"], _SOURCE_PATH_RE, "Projekt-Quellpfad")
    for field in ("name", "source_path"):
        values = [project[field] for project in projects]
        if len(values) != len(set(values)):
            _invalid(f"doppeltes Projektfeld {field}")
    project_codes = [project_code_for_name(project["name"]) for project in projects]
    # Zwei Projekte dürfen nicht auf denselben historischen Liefercode abbilden.
    if len(project_codes) != len(set(project_codes)):
        _invalid("doppelte Zuordnung eines Liefercodes")

    uebergabeprofile = mandant["uebergabeprofile"]
    if not isinstance(uebergabeprofile, dict) or not uebergabeprofile:
        _invalid("Übergabeprofile")
    for uebergabeprofil in uebergabeprofile.values():
        uebergabeprofil = _object(
            uebergabeprofil, {"assignment", "stage"}, "Übergabeprofil"
        )
        # Für Übergabeprofile gilt ausschließlich die Allowlist der
        # CodePipeline-Stages.
        if (
            not isinstance(uebergabeprofil["stage"], str)
            or uebergabeprofil["stage"] not in JCL_LEVELS
        ):
            _invalid("CodePipeline-Stage")
    return cast(MandantConfig, mandant)


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
