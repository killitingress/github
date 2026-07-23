"""Liest die kleine versionierte Lieferkonfiguration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from .errors import DeliveryError, Status


# Vorhandene Mandantenkürzel bestimmen Dateinamen und Mainframe-Member.
MANDANTEN_KUERZEL = {"FI", "BY", "LH", "NW", "OS", "SA", "IT"}
# ISPW-Instanz des Mandanten: T für Test, P für Produktion; steuert JCL und Mainframe-Ziel.
ISPW_INSTANZEN = {"T", "P"}
# Ausschließlich diese produktiv vorhandenen CodePipeline-Stages sind erlaubt.
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}
# Dieser aktuelle Referenzstand macht Abweichungen der Mandanten-Repositories
# sichtbar, ohne die technisch verarbeitbare Projektstruktur festzuschreiben.
PROJEKTREFERENZ = {
    "mtext-fi": (
        "FI",
        {
            "Configuration",
            "Fonts",
            "LOMS_Framework",
            "LOMS_Basis",
            "LOMS_PKA",
        },
    ),
    "mtext-autonom": ("IT", {"LOMS_Autonom"}),
    "mtext-by": ("BY", {"LOMS_Basis[BY]", "LOMS_Autonom[BY]"}),
    "mtext-lh": ("LH", {"LOMS_Basis[LH]", "LOMS_Autonom[LH]"}),
    "mtext-nw": ("NW", {"LOMS_Basis[NW]", "LOMS_Autonom[NW]"}),
    "mtext-os": ("OS", {"LOMS_Basis[OS]", "LOMS_Autonom[OS]"}),
    "mtext-sa": ("SA", {"LOMS_Basis[SA]", "LOMS_Autonom[SA]"}),
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
    ispw: str
    subsystem: str
    projects: dict[str, str]
    hostprofile: dict[str, dict[str, str]]
    releaselinien: dict[str, dict[str, str]]
    warnungen: tuple[str, ...]


class _MandantFields(NamedTuple):
    """Transportiert geprüfte Mandantenfelder zur vollständigen Konfiguration."""

    kuerzel: str
    repository: str
    ispw: str
    subsystem: str
    hostprofile: dict[str, dict[str, str]]
    excluded_projects: tuple[str, ...]


def _read_json(path: str | Path) -> Any:
    """Liest eine JSON-Datei und übersetzt nur tatsächliche I/O-Fehler."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"Konfiguration kann nicht gelesen werden: {Path(path).name}",
        ) from exc


def _read_mandant_configuration(
    path: str | Path, repository_name: str
) -> _MandantFields:
    """Validiert die Mandantendatei als eigenständige fachliche Eingabegrenze."""

    mandant_configuration = _read_json(path)
    if (
        not isinstance(mandant_configuration, dict)
        or "mandant" not in mandant_configuration
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Konfiguration ist unvollständig"
        )
    mandant = mandant_configuration["mandant"]
    if not isinstance(mandant, dict):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Konfiguration ist unvollständig"
        )

    try:
        kuerzel = mandant["kuerzel"]
        repository = mandant["repository"]
        ispw = mandant["ispw"]
        subsystem = mandant["subsystem"]
        hostprofile = mandant["hostprofile"]
        excluded = mandant.get("excluded_projects", [])
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
    if not isinstance(ispw, str) or ispw not in ISPW_INSTANZEN:
        raise DeliveryError(Status.VALIDATION_FAILED, "ISPW-Instanz ist ungültig")
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

    return _MandantFields(
        kuerzel=kuerzel,
        repository=repository,
        ispw=ispw,
        subsystem=subsystem,
        hostprofile=hostprofile,
        excluded_projects=tuple(excluded),
    )


def _scan_projects(
    root: Path, kuerzel: str, excluded_projects: tuple[str, ...]
) -> dict[str, str]:
    """Liest Projektverzeichnisse und besitzt die Ableitung ihrer Projektcodes."""

    try:
        project_paths = [
            item
            for item in root.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and item.name not in excluded_projects
        ]
        # Synchronisation und Archivbau dürfen keine Pfade außerhalb des
        # ausgecheckten Projektstands übernehmen.
        for project in project_paths:
            if project.is_symlink() or any(
                item.is_symlink() for item in project.rglob("*")
            ):
                raise DeliveryError(
                    Status.VALIDATION_FAILED,
                    "Projektstruktur enthält einen Symlink",
                )
    except OSError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Repository kann nicht gelesen werden"
        ) from exc
    projects: dict[str, str] = {}
    for project in sorted(project_paths, key=lambda item: item.name):
        # Diese Stelle besitzt die Formatregel für den Projektcode, der in
        # Paketnamen und Mainframe-Member eingeht.
        name = project.name
        base = name.removesuffix(f"[{kuerzel}]")
        projects[name] = base.removeprefix("LOMS_")[:5].upper()
    if not projects or len(projects.values()) != len(set(projects.values())):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "abgeleitete Projektcodes sind nicht eindeutig"
        )
    return projects


def _reference_warnings(
    repository: str, kuerzel: str, projects: dict[str, str]
) -> tuple[str, ...]:
    """Hält den unverbindlichen Projekt-Referenzabgleich aus der Validierung heraus."""

    warnungen: list[str] = []
    referenz = PROJEKTREFERENZ.get(repository)
    if referenz is None:
        warnungen.append(
            f"Repository besitzt keinen aktuellen Projekt-Referenzstand: {repository}"
        )
    else:
        referenz_kuerzel, referenz_projekte = referenz
        if kuerzel != referenz_kuerzel:
            warnungen.append(
                "Mandantenkürzel weicht vom aktuellen Referenzstand ab: "
                f"{repository} erwartet {referenz_kuerzel}, konfiguriert ist {kuerzel}"
            )
        fehlend = sorted(referenz_projekte - projects.keys())
        zusaetzlich = sorted(projects.keys() - referenz_projekte)
        if fehlend:
            warnungen.append(
                "Projekte fehlen gegenüber dem aktuellen Referenzstand: "
                + ", ".join(fehlend)
            )
        if zusaetzlich:
            warnungen.append(
                "Projekte sind gegenüber dem aktuellen Referenzstand zusätzlich: "
                + ", ".join(zusaetzlich)
            )
    return tuple(warnungen)


def _read_releaselinien(
    path: str | Path, hostprofile: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    """Validiert die zentrale Releaselinien-Zuordnung gegen die Hostprofile."""

    releaselinien = _read_json(path)
    if not isinstance(releaselinien, dict) or not releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinien fehlen")
    for values in releaselinien.values():
        if (
            not isinstance(values, dict)
            or not isinstance(values.get("etaps_linie"), str)
            or values.get("hostprofil") not in hostprofile
        ):
            raise DeliveryError(
                Status.VALIDATION_FAILED, "Releaselinie ist ungültig"
            )
    return releaselinien


def load_configuration(
    mandant_path: str | Path,
    releaselinien_path: str | Path,
    *,
    repository_name: str,
    repository_root: str | Path,
) -> Configuration:
    """Lädt den Mandanten aus dem Repository und verknüpft ihn mit den Releaselinien."""

    root = Path(repository_root)
    mandant_file = Path(mandant_path)
    # Ein relativer Mandantenpfad bezeichnet immer eine Datei im ausgecheckten
    # Mandanten-Repository und ist unabhängig vom Arbeitsverzeichnis des Aufrufers.
    if not mandant_file.is_absolute():
        mandant_file = root / mandant_file

    mandant = _read_mandant_configuration(mandant_file, repository_name)
    projects = _scan_projects(
        root, mandant.kuerzel, mandant.excluded_projects
    )
    releaselinien = _read_releaselinien(
        releaselinien_path, mandant.hostprofile
    )
    return Configuration(
        kuerzel=mandant.kuerzel,
        repository=mandant.repository,
        ispw=mandant.ispw,
        subsystem=mandant.subsystem,
        projects=projects,
        hostprofile=mandant.hostprofile,
        releaselinien=releaselinien,
        warnungen=_reference_warnings(
            mandant.repository, mandant.kuerzel, projects
        ),
    )
