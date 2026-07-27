"""Lädt und prüft die versionierte Konfiguration der Lieferworkflows.

Das Modul verbindet zentral gepflegte Mandanten- und Releaselinienzuordnungen
mit der Konfiguration und den Projektverzeichnissen des ausgecheckten
Repositories. Alle späteren Lieferschritte erhalten so ein geprüftes,
unveränderliches Eingabemodell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from .process import DeliveryError, Status


# Die gemeinsamen Zuordnungen werden relativ zum ausgecheckten Automationscode
# aufgelöst. Das Arbeitsverzeichnis des Aufrufers kann dadurch nicht unbemerkt
# eine andere Konfiguration auswählen.
AUTOMATION_ROOT = Path(__file__).resolve().parents[2]

# Diese ISPW-Instanzen sind im aktuellen Liefervertrag abgebildet. Der gewählte
# Wert steuert die JCL-Erzeugung und die zugehörigen Mainframe- und
# CodePipeline-Umgebungen.
ISPW_INSTANZEN = {"T", "P"}

# Hostprofile dürfen auf diese sechs eingerichteten CodePipeline-Stages zeigen.
# Die Liste an dieser Stelle macht das Modul zum Eigentümer dieses externen Vertrags.
CODEPIPELINE_STAGES = {"FKTE", "FKTF", "JURJ", "JURP", "SVTS", "VPTV"}

# Dieser Referenzbestand macht fehlende oder zusätzliche Projektverzeichnisse
# als Warnungen sichtbar, ohne den aktuellen Betriebsstand zu einer
# Validierungsregel zu machen.
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
    """Enthält die geprüften Eingaben, die alle Lieferabläufe gemeinsam verwenden.

    Die Konfiguration wird einmal an der Workflow-Grenze aufgebaut. Paketbau,
    Synchronisation und Übergabe müssen die Repositorydaten dadurch nicht
    jeweils neu auslegen.
    """

    repository: str
    kuerzel: str
    ispw: str
    subsystem: str
    projects: dict[str, str]
    hostprofile: dict[str, dict[str, str]]
    releaselinien: dict[str, dict[str, str]]
    warnungen: tuple[str, ...]


@dataclass(frozen=True)
class MandantStamm:
    """Beschreibt die zentrale Identität eines Mandanten-Repositories.

    Die Zuordnung verhindert, dass eine Datei im Repository das `kuerzel` oder
    Mainframe-Subsystem eines anderen Mandanten beansprucht.
    """

    repository: str
    subsystem: str


class _MandantFields(NamedTuple):
    """Transportiert geprüfte Mandantenfelder beim Aufbau des vollständigen Modells.

    Das interne Tupel benennt das Zwischenergebnis ausdrücklich, ohne einen
    zweiten öffentlichen Konfigurationstyp einzuführen.
    """

    kuerzel: str
    ispw: str
    subsystem: str
    hostprofile: dict[str, dict[str, str]]
    excluded_projects: tuple[str, ...]


def _read_json(path: str | Path) -> Any:
    """Liest eine Konfigurationsdatei und vereinheitlicht Fehler an der Dateigrenze.

    Die Aufrufer prüfen anschließend die fachliche Struktur des Dokuments. Diese
    Funktion verhindert, dass Details von Dekodierungs- und I/O-Fehlern in die
    Workflow-Ausgabe gelangen.
    """

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = f"Konfiguration kann nicht gelesen werden: {Path(path).name}"
        raise DeliveryError(Status.VALIDATION_FAILED, message) from exc


def load_mandanten_zuordnung(path: str | Path) -> dict[str, MandantStamm]:
    """Lädt die verbindliche Zuordnung vom `kuerzel` zur Repositoryidentität.

    Repositorynamen müssen eindeutig sein, weil die Zuordnung später belegt,
    dass das ausgecheckte Repository zum lokal angegebenen Mandanten gehört.
    """

    mandanten = _read_json(path)
    if not isinstance(mandanten, dict) or not mandanten:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")

    zuordnung: dict[str, MandantStamm] = {}
    repositories: set[str] = set()
    for kuerzel, values in mandanten.items():
        if (
            not isinstance(kuerzel, str)
            or not kuerzel
            or not isinstance(values, dict)
            or not isinstance(values.get("repository"), str)
            or not values["repository"]
            or not isinstance(values.get("subsystem"), str)
            or not values["subsystem"]
        ):
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist ungültig")
        repository = values["repository"]
        if repository in repositories:
            raise DeliveryError(Status.VALIDATION_FAILED, "Mandantenzuordnung ist nicht eindeutig")
        repositories.add(repository)
        zuordnung[kuerzel] = MandantStamm(repository=repository, subsystem=values["subsystem"])
    return zuordnung


def load_releaselinien_zuordnung(path: str | Path) -> dict[str, Any]:
    """Lädt die zentral gepflegte Zuordnung der aktiven Releaselinien.

    Die vollständige Prüfung hängt von den Hostprofilen des Mandanten ab und
    erfolgt deshalb erst beim Aufbau der fertigen Konfiguration.
    """

    releaselinien = _read_json(path)
    if not isinstance(releaselinien, dict) or not releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinien fehlen")
    return releaselinien


def _read_mandant_configuration(
    path: str | Path,
    mandanten_zuordnung: dict[str, MandantStamm],
    repository_name: str,
) -> _MandantFields:
    """Prüft die Mandantenangaben des Repositories gegen die zentralen Stammdaten.

    Der Abgleich bindet das lokale `kuerzel` an das vom Workflow übergebene
    Repository und prüft die später für Host- und Mainframe-Auswahl benötigten
    Felder.
    """

    mandant_configuration = _read_json(path)
    if not isinstance(mandant_configuration, dict) or "mandant" not in mandant_configuration:
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig")
    mandant = mandant_configuration["mandant"]
    if not isinstance(mandant, dict):
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig")

    try:
        kuerzel = mandant["kuerzel"]
        ispw = mandant["ispw"]
        hostprofile = mandant["hostprofile"]
        excluded = mandant.get("excluded_projects", [])
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Konfiguration ist unvollständig") from exc

    mandant_stammdaten = mandanten_zuordnung.get(kuerzel)
    if not isinstance(kuerzel, str) or mandant_stammdaten is None or repository_name != mandant_stammdaten.repository:
        raise DeliveryError(Status.VALIDATION_FAILED, "Mandant passt nicht zum Repository")
    if not isinstance(ispw, str) or ispw not in ISPW_INSTANZEN:
        raise DeliveryError(Status.VALIDATION_FAILED, "ISPW-Instanz ist ungültig")
    if not isinstance(excluded, list) or not all(isinstance(item, str) for item in excluded):
        raise DeliveryError(Status.VALIDATION_FAILED, "ausgeschlossene Projekte sind ungültig")
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
        ispw=ispw,
        subsystem=mandant_stammdaten.subsystem,
        hostprofile=hostprofile,
        excluded_projects=tuple(excluded),
    )


def _scan_projects(root: Path, kuerzel: str, excluded_projects: tuple[str, ...]) -> dict[str, str]:
    """Ermittelt lieferbare Projekte und leitet ihre externen Projektcodes ab.

    Ausgeschlossene und versteckte Verzeichnisse entfallen vor der Pfadprüfung.
    Die zurückgegebenen Codes werden Teil von Paketnamen und Mainframe-Membern.
    Kollisionen werden deshalb vor dem Artefaktbau abgelehnt.
    """

    try:
        project_paths = [
            item
            for item in root.iterdir()
            if item.is_dir()
            and not item.name.startswith(".")
            and item.name not in excluded_projects
        ]
        # Symlinks könnten Synchronisation oder Archivbau auf Inhalte außerhalb
        # des ausgecheckten Projektstands lenken und werden deshalb hier abgelehnt.
        for project in project_paths:
            if project.is_symlink() or any(item.is_symlink() for item in project.rglob("*")):
                raise DeliveryError(Status.VALIDATION_FAILED, "Projektstruktur enthält einen Symlink")
    except OSError as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, "Repository kann nicht gelesen werden") from exc
    projects: dict[str, str] = {}
    for project in sorted(project_paths, key=lambda item: item.name):
        # Der externe Projektcode wird an einer Stelle abgeleitet, weil Paketnamen
        # und Mainframe-Member denselben Wert verwenden.
        name = project.name
        base = name.removesuffix(f"[{kuerzel}]")
        projects[name] = base.removeprefix("LOMS_")[:5].upper()
    if not projects or len(projects.values()) != len(set(projects.values())):
        raise DeliveryError(Status.VALIDATION_FAILED, "abgeleitete Projektcodes sind nicht eindeutig")
    return projects


def _reference_warnings(kuerzel: str, projects: dict[str, str]) -> tuple[str, ...]:
    """Vergleicht die gefundenen Projekte mit dem unverbindlichen Referenzbestand.

    Abweichungen sind für den Betrieb hilfreich, machen eine Lieferung aber
    nicht ungültig. Getrennte Warnungen bewahren diese Unterscheidung für alle
    Aufrufer.
    """

    warnungen: list[str] = []
    referenz = PROJEKTREFERENZ.get(kuerzel)
    if referenz is None:
        warnungen.append(f"Mandant besitzt keinen aktuellen Projekt-Referenzstand: {kuerzel}")
    else:
        fehlend = sorted(referenz - projects.keys())
        zusaetzlich = sorted(projects.keys() - referenz)
        if fehlend:
            warnungen.append("Projekte fehlen gegenüber dem aktuellen Referenzstand: " + ", ".join(fehlend))
        if zusaetzlich:
            warnungen.append(
                "Projekte sind gegenüber dem aktuellen Referenzstand zusätzlich: "
                + ", ".join(zusaetzlich)
            )
    return tuple(warnungen)


def load_configuration(repository_root: str | Path, repository_name: str) -> Configuration:
    """Baut die vollständige Konfiguration eines ausgecheckten Repositories auf.

    Zentrale Zuordnungen, Mandantenangaben und gefundene Projekte werden hier
    verbunden. Nachfolgende Abläufe können sich dadurch auf ein einheitlich
    geprüftes Modell stützen.
    """

    root = Path(repository_root)
    mandanten_zuordnung = load_mandanten_zuordnung(AUTOMATION_ROOT / "config/mandanten.json")
    mandant = _read_mandant_configuration(root / ".github/config.json", mandanten_zuordnung, repository_name)
    projects = _scan_projects(root, mandant.kuerzel, mandant.excluded_projects)
    releaselinien = load_releaselinien_zuordnung(AUTOMATION_ROOT / "config/releaselinien.json")
    for values in releaselinien.values():
        if (
            not isinstance(values, dict)
            or not isinstance(values.get("etaps_linie"), str)
            or values.get("hostprofil") not in mandant.hostprofile
        ):
            raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist ungültig")
    return Configuration(
        repository=repository_name,
        kuerzel=mandant.kuerzel,
        ispw=mandant.ispw,
        subsystem=mandant.subsystem,
        projects=projects,
        hostprofile=mandant.hostprofile,
        releaselinien=releaselinien,
        warnungen=_reference_warnings(mandant.kuerzel, projects),
    )
