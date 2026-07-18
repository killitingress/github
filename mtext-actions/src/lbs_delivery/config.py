"""Lädt die Mandantenkonfiguration und kennt die festen Delivery-Ziele."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .delivery_names import project_code_for_name
from .errors import DeliveryError, Status


JsonObject = dict[str, Any]
MandantConfig = JsonObject
ReleaseLines = dict[str, dict[str, str]]

_RELEASE_LINE_RE = re.compile(r"R[0-9]{3}")
_RELEASE_TAG_RE = re.compile(r"R[0-9]{3}\.[0-9]{3}")
_REPOSITORY_RE = re.compile(r"mtext-(?:[a-z]{2}|autonom)")
_SUBSYSTEM_RE = re.compile(r"[A-Z0-9]{2,8}")
_PROJECT_NAME_RE = re.compile(r"[A-Za-z0-9_\[\]-]{1,128}")
_SOURCE_PATH_RE = re.compile(r"(?!/)(?!.*(?:^|/)\.\.(?:/|$))[^\x00]{1,256}")
_ASSIGNMENT_RE = re.compile(r"[A-Z0-9]{1,12}")
_MANDANT_CODES = {"FI", "BY", "LH", "NW", "OS", "SA", "IT"}
_HANDOVER_PROFILES = {"FKT", "JUR"}
_JCL_LEVELS = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}
_TECHNICAL_LINE_RE = re.compile(r"en[0-9]{2}")
_SYNC_STAGES = {"Entwicklung": ("E", "e"), "Abnahme": ("A", "a")}
ADAPTER_PAYLOAD = {"mandant": "MAN", "institut": "INR"}


def _invalid(subject: str) -> None:
    raise DeliveryError(Status.VALIDATION_FAILED, f"invalid {subject}")


def _object(value: Any, keys: set[str], subject: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != keys:
        _invalid(subject)
    return value


def _matches(value: Any, pattern: re.Pattern[str], subject: str) -> str:
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
            f"cannot read structured configuration {config_path.name}",
        ) from exc
    if not isinstance(document, dict):
        _invalid("configuration")
    return document


def load_mandant_config(
    config_path: str | Path, *, repository_name: str
) -> MandantConfig:
    """Lädt und prüft die einzige variable Delivery-Konfiguration."""

    document = load_document(config_path)
    _object(document, {"mandant"}, "mandant configuration")
    mandant = _object(
        document["mandant"],
        {"code", "repository", "subsystem", "projects", "handover_profiles"},
        "mandant",
    )
    if not isinstance(mandant["code"], str) or mandant["code"] not in _MANDANT_CODES:
        _invalid("mandant code")
    _matches(mandant["repository"], _REPOSITORY_RE, "mandant repository")
    _matches(mandant["subsystem"], _SUBSYSTEM_RE, "mandant subsystem")
    if mandant["repository"] != repository_name:
        _invalid("mandant repository identity")

    projects = mandant["projects"]
    if not isinstance(projects, list) or not projects:
        _invalid("mandant projects")
    for project in projects:
        project = _object(project, {"name", "source_path"}, "project")
        _matches(project["name"], _PROJECT_NAME_RE, "project name")
        _matches(project["source_path"], _SOURCE_PATH_RE, "project source path")
    for field in ("name", "source_path"):
        values = [project[field] for project in projects]
        if len(values) != len(set(values)):
            _invalid(f"duplicate project {field}")
    project_codes = [project_code_for_name(project["name"]) for project in projects]
    if len(project_codes) != len(set(project_codes)):
        _invalid("duplicate delivery name mapping")

    profiles = _object(
        mandant["handover_profiles"], _HANDOVER_PROFILES, "handover profiles"
    )
    for profile in profiles.values():
        profile = _object(profile, {"assignment", "stage"}, "handover profile")
        _matches(profile["assignment"], _ASSIGNMENT_RE, "handover assignment")
        if not isinstance(profile["stage"], str) or profile["stage"] not in _JCL_LEVELS:
            _invalid("JCL level")
    return mandant


def load_release_lines(path: str | Path) -> ReleaseLines:
    """Lädt die kleine Zuordnung fachlicher zu technischen Linien."""

    document = load_document(path)
    if not document:
        _invalid("release lines")
    for name, release_line in document.items():
        _matches(name, _RELEASE_LINE_RE, "release line")
        release_line = _object(
            release_line, {"line", "handover_profile"}, "release line"
        )
        _matches(release_line["line"], _TECHNICAL_LINE_RE, "technical line")
        if (
            not isinstance(release_line["handover_profile"], str)
            or release_line["handover_profile"] not in _HANDOVER_PROFILES
        ):
            _invalid("handover profile")
    return document


def validate_release_line(release_lines: ReleaseLines, release_line: str) -> None:
    """Akzeptiert ausschließlich eine konfigurierte Releaselinie."""

    if release_line not in release_lines:
        _invalid("release line")


def validate_release_tag(release_lines: ReleaseLines, tag: str) -> None:
    """Prüft Format und konfigurierte Releaselinie eines Release-Tags."""

    if not isinstance(tag, str) or _RELEASE_TAG_RE.fullmatch(tag) is None:
        _invalid("release tag")
    validate_release_line(release_lines, tag[:4])


def release_branch(release_lines: ReleaseLines, release_line: str) -> str:
    """Liefert den festen Bereitstellungsbranch einer Releaselinie."""

    validate_release_line(release_lines, release_line)
    return f"{release_line}/Bereitstellung"


def release_profile(release_lines: ReleaseLines, release_line: str) -> str:
    """Liefert das feste Übergabeprofil einer Releaselinie."""

    validate_release_line(release_lines, release_line)
    return release_lines[release_line]["handover_profile"]


def resolve_sync_branch(
    release_lines: ReleaseLines, branch: str, environment: str
) -> str:
    """Prüft einen vorhandenen Sync-Branch gegen seine Zielstage."""

    release_line, separator, stage = branch.partition("/")
    validate_release_line(release_lines, release_line)
    if separator != "/" or environment not in _SYNC_STAGES or stage != environment:
        _invalid("sync branch")
    return release_line


def resolve_adapter_url(
    release_lines: ReleaseLines, release_line: str, environment: str
) -> str:
    """Liefert den festen Adapterendpunkt einer Linie und Sync-Stage."""

    validate_release_line(release_lines, release_line)
    if environment not in _SYNC_STAGES:
        _invalid("sync environment")
    line = release_lines[release_line]["line"]
    return f"https://{line}{_SYNC_STAGES[environment][1]}.ltoma.intern/vMtextAdapter/sync"


def resolve_server_sync_root(
    release_lines: ReleaseLines, release_line: str, environment: str
) -> str:
    """Liefert den festen serverSync-Pfad einer Linie und Sync-Stage."""

    validate_release_line(release_lines, release_line)
    if environment not in _SYNC_STAGES:
        _invalid("sync environment")
    line = release_lines[release_line]["line"]
    return f"/nfs/mtext/{line}{_SYNC_STAGES[environment][0]}/serverSync"
