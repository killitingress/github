"""Erzeugt das gemeinsame M/Text-Projektpaket für Sync und Release.

Ein Projektpaket besteht aus einem F- oder D-Archiv und einer danebenliegenden
JSON-Informationsdatei. FULL-Lieferungen erhalten zusätzlich ein leeres
D-Archiv. Die Löschliste und die JSON-Elementliste entstehen aus derselben
ermittelten Änderungsmenge.
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


# Der gemeinsame Dateiname ordnet die Informationsdatei eindeutig einem
# Mandanten und Projekt zu.
INFORMATION_NAME = "_INFO_{kuerzel}-{project}.json"

# Beim Prüfsummenvergleich werden Archive blockweise gelesen, damit auch große
# FULL-Pakete keinen entsprechend großen Arbeitsspeicher benötigen.
_HASH_BLOCK_SIZE = 1024 * 1024

# Zwischenrelease `100` bezeichnet das Hauptrelease und wird als FULL geliefert.
# Spätere Zwischenreleases liefern die Änderungen gegenüber diesem Stand.
_FULL_RELEASE = "100"


@dataclass(frozen=True)
class PackageStand:
    """Bezugsstand, Zielstand und Git-Änderungen für Sync und Release."""

    von: tuple[str, str] | None
    bis: tuple[str, str]
    changes: Iterable[git.GitChange]


@dataclass(frozen=True)
class ProjectPackage:
    """Erzeugtes Projektpaket mit Informationsdatei und Archiven."""

    # JSON mit Stand, Elementliste und Prüfsummen
    information: Path
    # D-Archiv mit Änderungen und Löschliste, bei FULL ohne Änderungen
    d_archiv: Path
    # Vollständiger Projektbaum eines FULL, bei DELTA nicht vorhanden
    f_archiv: Path | None


# Bezugsstand und projektbezogene Elementliste für FULL- und DELTA-Lieferungen.
def release_scope(
    repository_root: Path,
    target_sha: str,
    *,
    releaselinie: str,
    zwischenrelease: str,
) -> tuple[tuple[str, str] | None, list[git.GitChange]]:
    """Bestimmt den Git-Vergleich aus den geprüften Bestandteilen des Liefer-Tags.

    Ein FULL hat keinen Bezugsstand. Ein DELTA vergleicht mit dem FULL-Tag
    derselben Releaselinie, damit jede Lieferung ohne die vorherigen DELTA-Lieferungen
    eingespielt werden kann.
    """

    # FULL hat keinen Bezugsstand und keinen Git-Vergleich.
    if zwischenrelease == _FULL_RELEASE:
        return None, []

    # DELTA vergleicht kumulativ mit der `.100`-Lieferung derselben Releaselinie.
    base_reference = f"r{releaselinie}.{_FULL_RELEASE}"
    base_sha = git.resolve(repository_root, f"refs/tags/{base_reference}")
    git.require_ancestor(repository_root, base_sha, target_sha)
    return (base_reference, base_sha), git.changes(repository_root, base_sha, target_sha)


def project_elements(
    repository_root: Path,
    project: str,
    *,
    base: tuple[str, str] | None,
    changes: Iterable[git.GitChange],
) -> list[list[str]]:
    """Ermittelt die projektbezogene Elementliste für Paket und Vorprüfung.

    Ein fehlender Bezugsstand bezeichnet ein FULL mit allen Dateien als
    hinzugefügt. Andernfalls übernimmt ein DELTA Status und Pfade aus dem
    bereits bestimmten Git-Vergleich.
    """

    # FULL: alle Projektdateien als hinzugefügt melden.
    if base is None:
        return [
            ["A", path.relative_to(repository_root / project).as_posix()]
            for path in sorted((repository_root / project).rglob("*"))
            if path.is_file()
        ]

    # DELTA: Status und Pfade aus dem bereits bestimmten Git-Vergleich übernehmen.
    return [
        [status, Path(path).relative_to(project).as_posix()]
        for status, path in git.project_changes(changes, project)
    ]


# F- und D-Archive sowie ihre Prüfsummen erzeugen.
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
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Projektarchiv kann nicht erzeugt werden") from exc


def _write_delta_archive(
    archive_path: Path,
    repository_root: Path,
    project: str,
    deletion_list: str,
    elements: list[list[str]],
) -> None:
    """Erzeugt ein D-Archiv aus der gemeinsamen Elementliste.

    Die JSON-Pfade sind projektbezogen. Für Archiv und Löschliste wird daraus
    der repositorybezogene Pfad mit vorangestelltem Projektverzeichnis.
    """

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        deleted: list[str] = []

        try:
            # Geänderte Dateien nach Staging kopieren, Löschungen nur sammeln.
            (staging / project).mkdir(parents=True)
            for status, relative in elements:
                repository_relative = Path(project, relative)
                if status == "D":
                    deleted.append(repository_relative.as_posix())
                    continue

                destination = staging / repository_relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repository_root / repository_relative, destination)

            # Löschliste und Archivinhalt im Staging bereitstellen.
            (staging / deletion_list).write_text(
                "".join(f"{path}\n" for path in deleted),
                encoding="utf-8",
            )
            entries = [item.name for item in sorted(staging.iterdir())]
        except OSError as exc:
            raise DeliveryError(Status.PACKAGE_FAILED, "DELTA-Inhalt kann nicht bereitgestellt werden") from exc

        _write_archive(archive_path, staging, entries)


def _sha256(path: Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer erzeugten Archivdatei."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as package:
            while block := package.read(_HASH_BLOCK_SIZE):
                digest.update(block)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Projektarchiv kann nicht geprüft werden") from exc
    return digest.hexdigest()


# Gemeinsame Paketerzeugung für Sync und Release.
def build_project_package(
    configuration: Configuration,
    *,
    repository_root: Path,
    output_directory: Path,
    project: str,
    stand: PackageStand,
) -> ProjectPackage:
    """Erzeugt Archive und JSON-Informationsdatei für ein Projekt.

    Sync und Release verwenden dasselbe Paketformat. `stand` beschreibt den
    Vergleichsrahmen: Bei FULL entfällt `stand.von`, bei DELTA liefert
    `stand.changes` die gemeinsame Elementliste für Archiv, Löschliste und
    Informationsdatei.
    """

    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Paketausgabeverzeichnis kann nicht erstellt werden") from exc

    # Gemeinsame Elementliste für Archiv, Löschliste und Informationsdatei.
    elements = project_elements(repository_root, project, base=stand.von, changes=stand.changes)

    prefix = f"{configuration.kuerzel}{configuration.projects[project]}"
    full_archive = None
    if stand.von is None:
        full_archive = output_directory / f"{prefix}F.tgz"
        _write_archive(full_archive, repository_root, [f"./{project}"])

    # D-Archiv entsteht immer. Bei FULL bleibt die Änderungsmenge leer.
    delta_archive = output_directory / f"{prefix}D.tgz"
    _write_delta_archive(
        delta_archive,
        repository_root,
        project,
        f"{prefix}D.txt",
        [] if stand.von is None else elements,
    )

    # Stand, Prüfsummen und Elementliste in der Informationsdatei ablegen.
    stand_json: dict[str, object] = {
        "bis": {"referenz": stand.bis[0], "commit": stand.bis[1]},
    }
    if stand.von is not None:
        stand_json["von"] = {"referenz": stand.von[0], "commit": stand.von[1]}

    checksums = {"D": _sha256(delta_archive)}
    if full_archive is not None:
        checksums["F"] = _sha256(full_archive)

    information = output_directory / INFORMATION_NAME.format(kuerzel=configuration.kuerzel, project=project)
    try:
        information.write_text(
            json.dumps(
                {
                    "projekt": project,
                    "stand": stand_json,
                    "elemente": elements,
                    "sha256": checksums,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Informationsdatei kann nicht geschrieben werden") from exc

    return ProjectPackage(information=information, d_archiv=delta_archive, f_archiv=full_archive)
