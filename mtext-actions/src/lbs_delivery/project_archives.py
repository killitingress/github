"""Archiv-Erzeugung für Tonic-Projekte - wird aus Synchronisation und
Release-Pipeline aufgerufen.

Zu jedem Tonic-Projekt (z.B. "LOMS_Basis") entstehen für Synchronisation und
Release F- und/oder D-Archive (welche die entsprechenden Änderungen enthalten)
und daneben jeweils eine Info-Datei im JSON-Format für die Nachkontrolle.
F-Archive sind für Voll-Lieferungen - enthalten also den kompletten Projektbaum,
während D-Archive nur geänderte Dateien und eine Löschliste enthalten (Delta).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import git
from .config import Configuration
from .process import DeliveryError, Status


# Name der Info-Datei - übernommen aus der Konvention im trans/ Verzeichnis
INFORMATION_NAME = "_INFO_{kuerzel}-{project}.json"

# beim Paketbau erstellter Bericht für die Beschreibung des GitHub Releases
RELEASE_REPORT_NAME = "lieferbericht.md"


@dataclass(frozen=True)
class Scope:
    """Vergleichsstände und Git-Änderungen für Archiv oder Vorrelease-Bericht."""

    von: tuple[str, str] | None
    bis: tuple[str, str]
    changes: list[git.GitChange]


@dataclass(frozen=True)
class ProjectArchives:
    """Hält die erzeugte Informationsdatei und die Archive eines Projekts."""

    # JSON mit Scope, Elementliste und Prüfsumme des F- oder D-Archivs
    information: Path
    # D-Archiv mit Änderungen oder leerer Löschliste bei FULL
    d_archiv: Path
    # Vollständiger Projektbaum eines FULL, bei DELTA nicht vorhanden
    f_archiv: Path | None


def delta_scope(repository: Path, von: tuple[str, str], bis: tuple[str, str]) -> Scope:
    """Liest die Git-Änderungen zwischen zwei Ständen als Delta-Scope."""

    return Scope(von=von, bis=bis, changes=git.changes(repository, von[1], bis[1]))


def release_scope(repository_root: Path, tag: str, commit: str) -> Scope:
    """Ermittelt den Scope der Änderungen für das Liefer-Tag.

    Ein FULL hat keinen Bezugsstand. Ein DELTA vergleicht mit dem .100-Tag
    derselben Releaselinie, damit jede Lieferung ohne die vorherigen
    DELTA-Lieferungen eingespielt werden kann.
    """

    tag_match = git.LIEFER_TAG_RE.fullmatch(tag)
    releaselinie = tag_match.group("releaselinie")
    zwischenrelease = tag_match.group("zwischenrelease")

    # FULL hat keinen Bezugsstand und keinen Diff.
    if zwischenrelease == "100":
        return Scope(von=None, bis=(tag, commit), changes=[])

    # DELTA vergleicht kumulativ mit der `.100`-Lieferung derselben Releaselinie
    base_reference = f"r{releaselinie}.100"
    base_sha = git.resolve(repository_root, f"refs/tags/{base_reference}")

    # Sicherstellen, dass der Commit auf der Releaselinie basiert, sonst enden
    # wir hier mit SOURCE_FAILED.
    git.require_ancestor(repository_root, base_sha, commit)

    return delta_scope(repository_root, (base_reference, base_sha), (tag, commit))


def project_elements(repository_root: Path, project: str, scope: Scope) -> list[list[str]]:
    """Gibt die Liste von geänderten Dateien mit Status und Pfad aus einem Scope zurück.

    Bei einer Voll-Lieferung (FULL) werden alle Dateien des Projekts als
    hinzugefügt gemeldet, bei einer Delta-Lieferung (DELTA) werden die Status
    und Pfade aus dem bereits bestimmten Git-Vergleich übernommen.
    """

    # FULL: alle Projektdateien als hinzugefügt melden.
    if scope.von is None:
        return [
            ["A", e.relative_to(repository_root / project).as_posix()]
            for e in sorted((repository_root / project).rglob("*"))
            if e.is_file()
        ]

    # DELTA: Status und Pfade aus dem bereits bestimmten Git-Vergleich übernehmen.
    return [
        [status, Path(path).relative_to(project).as_posix()]
        for status, path in git.project_changes(scope.changes, project)
    ]


def previous_release_scope(repository: Path, tag: str, commit: str) -> Scope:
    """Bestimmt den Delta-Scope für Lieferungen.

    Der höchste niedrigere Liefer-Tag bestimmt den Vorgänger, unabhängig vom Branch.
    """

    # gültige niedrigere Liefer-Tags zulassen, auch vor einem neuen Hauptrelease
    previous = max(
        e for e in git.execute(repository, "tag", "--list", "r*").decode().splitlines()
        if git.LIEFER_TAG_RE.fullmatch(e) and e < tag
    )

    # Änderungen seit dem Vorrelease unabhängig vom kumulativen Paketumfang ermitteln
    previous_sha = git.resolve(repository, f"refs/tags/{previous}")
    return delta_scope(repository, (previous, previous_sha), (tag, commit))


def release_report(
    configuration: Configuration,
    repository: Path,
    *,
    paket_scope: Scope,
    information_scope: Scope,
) -> str:
    """Beschreibt die Lieferung und beide Vergleiche für Vorprüfung und GitHub Release.

    `information_scope.von` enthält den vorherigen Liefer-Tag und dessen Commit.
    Der Paketumfang kann ein FULL ohne Bezugsstand sein.
    """

    # Liefer-Tag, Lieferart und Commit aus dem Paketumfang gemeinsam darstellen
    delivery_type = "FULL" if paket_scope.von is None else "DELTA"
    lines = [
        "## Lieferung",
        "",
        f"- Liefer-Tag: `{paket_scope.bis[0]}`",
        f"- Lieferart: `{delivery_type}`",
        f"- Commit: `{paket_scope.bis[1]}`",
        "",
        "`A`: hinzugefügt, `M`: geändert, `D`: gelöscht, `T`: Typ geändert",
        "",
    ]

    # Vorrelease-Vergleich und Lieferumfang mit ihren jeweiligen Bezugsständen benennen
    sections = [
        (f"Änderungen seit `{information_scope.von[0]}`", information_scope),
        ("Lieferumfang", paket_scope),
    ]

    # dieselbe Projektzuordnung wie beim Paketbau verwenden
    for heading, section in sections:
        lines.extend((f"## {heading}", ""))

        # FULL beschreibt den Zielbestand, ein Diff nennt beide Vergleichsstände
        if section.von is None:
            lines.extend(("Vollständiger Projektstand (FULL).", ""))
        else:
            lines.extend((f"Vergleich: `{section.von[0]}` → `{section.bis[0]}`", ""))

        for project in configuration.projects:
            elements = project_elements(repository, project, section)
            lines.extend((f"### `{project}`", ""))

            # leere Vergleiche ausdrücklich als solche kennzeichnen
            if elements:
                lines.extend(f"- `{status}` `{path}`" for status, path in elements)
            else:
                lines.append("- Keine Änderungen")
            lines.append("")

    return "\n".join(lines)


def _write_archive(archive_path: Path, source_directory: Path, entries: Iterable[str]) -> None:
    """Erzeugt ein gzip-komprimiertes TAR-Archiv mit den angegebenen Einträgen."""

    try:
        subprocess.run(
            ["tar", "-czf", str(archive_path.resolve()), "--", *entries],
            cwd=source_directory,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"Archiv kann nicht erzeugt werden: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        # tar schreibt die Ursache nach stderr, nicht in die Exception-Meldung
        detail = (exc.stderr or b"").decode(errors="replace").strip() or str(exc)
        raise DeliveryError(Status.PACKAGE_FAILED, f"Archiv kann nicht erzeugt werden: {detail}") from exc


def _write_delta_archive(
    archive_path: Path,
    repository_root: Path,
    project: str,
    deletion_list: str,
    elements: list[list[str]],
) -> None:
    """Erzeugt ein D-Archiv aus der Elementliste."""

    # Wir kopieren alle geänderten Dateien (aus `elements`) in ein temporäres
    # Verzeichnis und dies wird dann zum *D.tgz Archiv.
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        deleted: list[str] = [] # Löschliste

        try:
            # Geänderte Dateien nach Staging kopieren, bzw. in Löschliste aufnehmen
            (staging / project).mkdir(parents=True)

            for status, relative_path in elements:
                repository_relative = Path(project, relative_path)

                if status == "D":
                    deleted.append(repository_relative.as_posix())
                    continue

                destination = staging / repository_relative
                destination.parent.mkdir(parents=True, exist_ok=True)

                shutil.copyfile(repository_root / repository_relative, destination)

            # Löschliste und Archivinhalt im Staging bereitstellen.
            (staging / deletion_list).write_text("".join(f"{e}\n" for e in deleted), encoding="utf-8")
            entries = [e.name for e in sorted(staging.iterdir())]

        except OSError as exc:
            raise DeliveryError(Status.PACKAGE_FAILED, f"DELTA-Inhalt kann nicht bereitgestellt werden: {exc}") from exc

        # .tgz Archiv erzeugen aus dem temporären Verzeichnis
        _write_archive(archive_path, staging, entries)


def _sha256(path: Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer Datei, blockweise."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as archive_file:
            while block := archive_file.read(1024 * 1024):  # 1 MB je Block
                digest.update(block)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"SHA-256-Prüfsumme kann nicht berechnet werden: {exc}") from exc

    return digest.hexdigest()


def build_project_archives(
    configuration: Configuration,
    repository_root: Path,
    project: str,
    output_directory: Path,
    *,
    paket_scope: Scope,
    information_scope: Scope,
) -> ProjectArchives:
    """Erzeugt Archive und JSON-Informationsdatei für ein Projekt.

    `paket_scope` bestimmt Lieferart, Archiv und Löschliste, `information_scope` die
    Vergleichsstände und Elementliste der JSON-Datei. Bei Mainframe-Lieferungen
    beschreibt die Information den Vergleich zum vorherigen Liefer-Tag.
    Synchronisationen verwenden für beide denselben Scope, bei FULL ohne `von`.
    Ein FULL enthält das F-Archiv und ein leeres D-Archiv.
    """

    # gemeinsames Ausgabeverzeichnis für Archive und Information bereitstellen
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"Ausgabeverzeichnis kann nicht erstellt werden: {exc}") from exc

    # Paketinhalt und Löschliste folgen dem Liefer- oder Synchronisationsumfang
    paket_elemente = project_elements(repository_root, project, paket_scope)

    # gemeinsames Namenspräfix für Archive und Löschliste bilden
    prefix = f"{configuration.kuerzel}{configuration.projects[project]}"

    # ein D-Archiv wird immer erzeugt, ein F-Archiv nur bei Voll-Lieferungen
    delta_archive = output_directory / f"{prefix}D.tgz"
    if paket_scope.von is None:
        lieferart = "FULL"
        _write_delta_archive(delta_archive, repository_root, project, f"{prefix}D.txt", [])
        full_archive = output_directory / f"{prefix}F.tgz"
        _write_archive(full_archive, repository_root, [f"./{project}"])
    else:
        lieferart = "DELTA"
        _write_delta_archive(delta_archive, repository_root, project, f"{prefix}D.txt", paket_elemente)
        full_archive = None

    # die Informationsdatei folgt ihrem eigenen Vergleichsumfang
    info_elemente = project_elements(repository_root, project, information_scope)

    # Bezugsstand und Zielstand gehören zum Vergleich der aufgeführten Elemente
    scope_json: dict[str, object] = {"bis": {"referenz": information_scope.bis[0], "commit": information_scope.bis[1]}}
    if information_scope.von is not None:
        scope_json["von"] = {"referenz": information_scope.von[0], "commit": information_scope.von[1]}

    # bei FULL das F-Archiv, bei DELTA das D-Archiv der Projektlieferung prüfen
    checksum = _sha256(full_archive if full_archive is not None else delta_archive)

    # Informationsdatei erzeugen
    information = output_directory / INFORMATION_NAME.format(kuerzel=configuration.kuerzel, project=project)
    try:
        information.write_text(
            json.dumps({
                "projekt": project, "lieferart": lieferart, "scope": scope_json,
                "elemente": info_elemente, "sha256": checksum,
            }, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"Informationsdatei kann nicht geschrieben werden: {exc}") from exc

    return ProjectArchives(information=information, d_archiv=delta_archive, f_archiv=full_archive)
