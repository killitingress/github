"""Liest die kleine versionierte Lieferkonfiguration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import DeliveryError, Status


# Vorhandene Mandantenkürzel bestimmen Dateinamen und Mainframe-Member.
MANDANTEN_KUERZEL = {"FI", "BY", "LH", "NW", "OS", "SA", "IT"}
# Ausschließlich diese produktiv vorhandenen CodePipeline-Stages sind erlaubt.
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}
# Historisch festgelegte Liefercodes bilden Projektname auf Archiv und Member ab.
PROJECT_CODES = {
    "Configuration": "CONFI",
    "Fonts": "FONTS",
    "LOMS_Framework": "FRAME",
    "LOMS_Basis": "BASIS",
    "LOMS_PKA": "PKA",
    "LOMS_Autonom": "AUTON",
}
# Entwicklungs- und Abnahmestage bestimmen serverSync-Pfad und Adapterhost.
SYNC_STAGES = {"Entwicklung": ("E", "e"), "Abnahme": ("A", "a")}
# Dieser Payload ist Bestandteil des bestehenden M/Text-Adaptervertrags.
ADAPTER_PAYLOAD = {"mandant": "MAN", "institut": "INR"}


@dataclass(frozen=True)
class Configuration:
    """Enthält die einmalig gelesenen Werte aller internen Abläufe."""

    kuerzel: str
    repository: str
    subsystem: str
    projects: dict[str, str]
    hostprofile: dict[str, dict[str, str]]
    releaselinien: dict[str, dict[str, str]]


def _read_json(path: str | Path) -> Any:
    """Liest eine JSON-Datei und übersetzt nur tatsächliche I/O-Fehler."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"Konfiguration kann nicht gelesen werden: {Path(path).name}",
        ) from exc


def load_configuration(
    mandant_path: str | Path,
    releaselinien_path: str | Path,
    *,
    repository_name: str,
    repository_root: str | Path,
) -> Configuration:
    """Lädt den Mandanten und verknüpft ihn mit den Releaselinien."""

    try:
        mandant = _read_json(mandant_path)["mandant"]
        kuerzel = mandant["kuerzel"]
        repository = mandant["repository"]
        subsystem = mandant["subsystem"]
        hostprofile = mandant["hostprofile"]
        excluded = mandant.get("excluded_projects", [])
        releaselinien = _read_json(releaselinien_path)
    except (KeyError, TypeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Konfiguration ist unvollständig"
        ) from exc

    if (
        not isinstance(kuerzel, str)
        or kuerzel not in MANDANTEN_KUERZEL
        or repository != repository_name
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Mandant passt nicht zum Repository"
        )
    if not isinstance(subsystem, str) or not subsystem:
        raise DeliveryError(Status.VALIDATION_FAILED, "Subsystem fehlt")
    if not isinstance(excluded, list) or not all(
        isinstance(item, str) for item in excluded
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "ausgeschlossene Projekte sind ungültig"
        )
    if not isinstance(hostprofile, dict) or not hostprofile:
        raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofile fehlen")
    for profile in hostprofile.values():
        if (
            not isinstance(profile, dict)
            or profile.get("stage") not in CODEPIPELINE_STAGES
            or not isinstance(profile.get("assignment"), str)
        ):
            raise DeliveryError(Status.VALIDATION_FAILED, "Hostprofil ist ungültig")

    root = Path(repository_root)
    try:
        names = sorted(
            item.name
            for item in root.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and item.name not in excluded
        )
    except OSError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Repository kann nicht gelesen werden"
        ) from exc
    projects: dict[str, str] = {}
    for name in names:
        base = name[:-4] if name.endswith(f"[{kuerzel}]") else name
        if base not in PROJECT_CODES:
            raise DeliveryError(
                Status.VALIDATION_FAILED,
                f"Projekt besitzt keinen Liefercode: {name}",
            )
        projects[name] = PROJECT_CODES[base]
    if not projects or len(projects.values()) != len(set(projects.values())):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Projektzuordnung ist nicht eindeutig"
        )

    if not isinstance(releaselinien, dict) or not releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinien fehlen")
    for values in releaselinien.values():
        if (
            not isinstance(values, dict)
            or not isinstance(values.get("mtext_linie"), str)
            or values.get("uebergabeprofil") not in hostprofile
        ):
            raise DeliveryError(
                Status.VALIDATION_FAILED, "Releaselinie ist ungültig"
            )
    return Configuration(
        kuerzel=kuerzel,
        repository=repository,
        subsystem=subsystem,
        projects=projects,
        hostprofile=hostprofile,
        releaselinien=releaselinien,
    )
