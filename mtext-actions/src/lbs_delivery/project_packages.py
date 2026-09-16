"""Erzeugt Projektpakete und Berichte für Synchronisierung und Lieferung."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from . import git
from .config import Configuration
from .process import DeliveryError, Status


@dataclass(frozen=True)
class Scope:
    """Hält Bezugsstand, Zielstand und die Änderungen eines Git-Vergleichs."""

    von: tuple[str, str] | None
    bis: tuple[str, str]
    changes: list[git.GitChange]


@dataclass(frozen=True)
class ProjectPackage:
    """Kapselt das Informations-Dokument (dict) und Archiv (Path) für ein Projekt."""

    information: dict[str, object]
    archive: Path


def delta_scope(repository: Path, von: tuple[str, str], bis: tuple[str, str]) -> Scope:
    """Ermittelt den Scope eines Deltas."""

    return Scope(von=von, bis=bis, changes=git.changes(repository, von[1], bis[1]))


def release_scope(repository_root: Path, tag: git.LieferTag, commit: str) -> Scope:
    """Ermittelt den Scope für ein Liefer-Tag.

    Ein FULL hat keinen Bezugsstand und keine Changes, und umfasst später alle
    Dateien des Projekts. Ein DELTA vergleicht gegen das FULL der passenden
    Releaselinie.
    """

    # FULL hat keinen Bezugsstand und keinen Diff, Release Scope ist dadurch alles
    if tag.ist_hauptrelease:
        return Scope(von=None, bis=(str(tag), commit), changes=[])

    # DELTA vergleicht kumulativ mit der `.100`-Lieferung derselben Releaselinie
    base_reference = str(git.LieferTag(tag.releaselinie, "100"))
    base_sha = git.resolve(repository_root, f"refs/tags/{base_reference}")

    # Sicherstellen, dass der Commit auf der Releaselinie basiert, sonst enden
    # wir hier mit SOURCE_FAILED
    git.require_ancestor(repository_root, base_sha, commit)

    return delta_scope(repository_root, (base_reference, base_sha), (str(tag), commit))


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


def previous_release_scope(repository: Path, tag: git.LieferTag, commit: str) -> Scope:
    """Bestimmt den Vergleich zum vorherigen Liefer-Tag.

    Vorheriger Tag ist der höchste vorhandene Liefer-Tag, der namentlich vor
    dem aktuellen liegt. Das gilt auch für ein neues Hauptrelease und ohne
    Rücksicht auf Branch oder Git-Abstammung.
    """

    # aus den vorhandenen Liefer-Tags den namentlich nächsten Vorgänger entnehmen
    tags = []
    for value in git.execute(repository, "tag", "--list", "r*").decode().splitlines():
        if not value:
            continue
        try:
            tags.append(git.LieferTag.parse(value))
        except ValueError:
            continue

    previous = max(e for e in tags if e < tag)
    previous_sha = git.resolve(repository, f"refs/tags/{previous}")

    return delta_scope(repository, (str(previous), previous_sha), (str(tag), commit))


def _project_sections(configuration: Configuration, repository: Path, scope: Scope) -> list[str]:
    """Stellt die nicht leeren Projektabschnitte für das Freigabe-Issue zusammen."""

    # jedes betroffene Projekt mit seinen Ressourcen aufführen
    lines: list[str] = []
    repository_url = (
        f"{os.environ['GITHUB_SERVER_URL'].rstrip('/')}/{os.environ['GITHUB_REPOSITORY']}"
    )
    for project in configuration.projects:
        elements = project_elements(repository, project, scope)
        if not elements:
            continue

        lines.extend((f"### `{project}`", ""))

        # vorhandene Elemente am festgehaltenen Ziel-Commit öffnen
        for status, path in elements:
            if status == "D":
                lines.append(f"- `{status}` `{path}`")
                continue

            repository_path = urllib.parse.quote(f"{project}/{path}", safe="/")
            file_url = f"{repository_url}/blob/{scope.bis[1]}/{repository_path}"
            lines.append(f"- `{status}` [`{path}`]({file_url})")
        lines.append("")
    return lines


def delivery_report(
    configuration: Configuration, repository: Path, *, paket_scope: Scope,
    vorrelease_scope: Scope, standzeilen: list[str],
) -> str:
    """Erstellt den Lieferumfang für das Freigabe-Issue als Markdown-Text."""

    lines = ["## Lieferung", "", *standzeilen, ""]

    # Abweichungen vom vorherigen Lieferstand ohne leere Projektabschnitte zeigen
    lines.extend((f"## Abweichungen gegenüber `{vorrelease_scope.von[0]}`", ""))
    lines.extend((f"Vergleich: `{vorrelease_scope.von[0]}` → `{vorrelease_scope.bis[0]}`", ""))
    changes = _project_sections(configuration, repository, vorrelease_scope)
    if changes:
        lines.extend(changes)
    else:
        lines.extend(("Keine Ressourcenänderungen in den gelieferten Projekten.", ""))

    # tatsächlichen Archivinhalt getrennt vom Vergleich zum vorherigen Liefer-Tag zeigen
    lines.extend(("## Inhalt der Projektarchive", ""))
    if paket_scope.von is None:
        lines.extend(("Vollständiger Projektstand (FULL).", ""))
    else:
        lines.extend((f"Vergleich: `{paket_scope.von[0]}` → `{paket_scope.bis[0]}`", ""))

    archive_contents = _project_sections(configuration, repository, paket_scope)
    if archive_contents:
        lines.extend(archive_contents)
    elif paket_scope.von is None:
        lines.extend(("Die Projektarchive enthalten keine Ressourcendateien.", ""))
    else:
        lines.extend(("Die Projektarchive enthalten keine geänderten oder gelöschten Ressourcen.", ""))

    return "\n".join(lines)


def _write_archive(target_name: Path, source_directory: Path, entries: Iterable[str]) -> None:
    """Erzeugt ein gzip-komprimiertes TAR-Archiv mit den angegebenen Einträgen."""

    try:
        subprocess.run(
            ["tar", "-czf", str(target_name), "--", *entries],
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


def project_archive_path(configuration: Configuration, project: str, directory: Path, art: str) -> Path:
    """Gibt den vollen Pfad eines F- oder D-Archivs zurück."""

    return directory / f"{configuration.kuerzel}{configuration.projects[project]}{art}.tgz"


def build_delta_archive(source: Path, project: str, target: Path, elements: list[list[str]]) -> None:
    """Erzeugt ein D-Archiv aus der Elementliste."""

    # geänderte Dateien und Löschliste in einem temporären "staging" Verzeichnis sammeln
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

                shutil.copyfile(source / repository_relative, destination)

            # Löschliste und Archivinhalt im Staging bereitstellen
            (staging / f"{target.stem}.txt").write_text(
                "".join(f"{e}\n" for e in deleted), encoding="utf-8",
            )
            entries = [e.name for e in sorted(staging.iterdir())]

        except OSError as exc:
            raise DeliveryError(Status.PACKAGE_FAILED, f"DELTA-Inhalt kann nicht bereitgestellt werden: {exc}") from exc

        # gesammelten Inhalt in das vorgegebene D-Archiv schreiben
        _write_archive(target, staging, entries)


def sha256_file(path: Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer Datei, blockweise."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as archive_file:
            while block := archive_file.read(1024 * 1024):  # 1 MB je Block
                digest.update(block)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"SHA-256-Prüfsumme kann nicht berechnet werden: {exc}") from exc

    return digest.hexdigest()


def build_project_archive(
    configuration: Configuration,
    repository_root: Path,
    project: str,
    output_directory: Path,
    scope: Scope,
) -> Path:
    """Erzeugt ein Projektarchiv für Synchronisierung oder Mainframe-Lieferung."""

    # Ausgabeverzeichnis für das Archiv vorbereiten
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, f"Ausgabeverzeichnis kann nicht erstellt werden: {exc}") from exc

    # FULL überträgt den Projektbaum, DELTA die geänderten Dateien
    if scope.von is None:
        archive = project_archive_path(configuration, project, output_directory, "F")
        _write_archive(archive, repository_root, [f"./{project}"])
    else:
        archive = project_archive_path(configuration, project, output_directory, "D")
        elements = project_elements(repository_root, project, scope)
        build_delta_archive(repository_root, project, archive, elements)

    return archive


def build_project_package(configuration: Configuration, repository_root: Path, project: str, output_directory: Path, scope: Scope) -> ProjectPackage:
    """Ergänzt das Projektarchiv um die Informationsdaten für den Adapter."""

    # Auftrag auf Bezugsstand, Zielstand und Archivart beziehen
    lieferart = "FULL" if scope.von is None else "DELTA"
    scope_json: dict[str, object] = {"bis": {"referenz": scope.bis[0], "commit": scope.bis[1]}}
    if scope.von is not None:
        scope_json["von"] = {"referenz": scope.von[0], "commit": scope.von[1]}

    # Archivinhalt bauen, ohne die interne Elementliste an den Adapter zu geben
    archive = build_project_archive(configuration, repository_root, project, output_directory, scope)

    # Prüfsumme des fertigen Archivs ergänzen
    return ProjectPackage(
        information={
            "projekt": project,
            "lieferart": lieferart,
            "scope": scope_json,
            "sha256": sha256_file(archive),
        },
        archive=archive,
    )
