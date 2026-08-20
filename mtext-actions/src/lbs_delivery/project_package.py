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
from pathlib import Path

from . import git
from .config import Configuration
from .process import DeliveryError, Status


# Der gemeinsame Dateiname ordnet die Informationsdatei eindeutig einem
# Mandanten und Projekt zu.
_INFORMATION_NAME = "_INFO_{kuerzel}-{project}.json"

# Beim Prüfsummenvergleich werden Archive blockweise gelesen, damit auch große
# FULL-Pakete keinen entsprechend großen Arbeitsspeicher benötigen.
_HASH_BLOCK_SIZE = 1024 * 1024

# Die Release-Version `100` bezeichnet die FULL-Lieferung einer Releaselinie.
# Jedes weitere Release der Linie liefert die Änderungen gegenüber diesem Stand.
_FULL_RELEASE = "100"


# Bezugsstand und projektbezogene Elementliste für FULL- und DELTA-Lieferungen.
def release_scope(
    repository_root: str | Path,
    tag: str,
    target_sha: str,
) -> tuple[tuple[str, str] | None, list[git.GitChange]]:
    """Bestimmt Bezugsstand und kumulativen Git-Vergleich eines Release-Tags.

    Ein FULL hat keinen Bezugsstand. Ein DELTA vergleicht mit dem FULL-Tag
    derselben Releaselinie, damit jede Lieferung ohne die Zwischenreleases
    eingespielt werden kann.
    """

    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")

    # FULL hat keinen Bezugsstand und keinen Git-Vergleich.
    if tag_match.group("release") == _FULL_RELEASE:
        return None, []

    # DELTA vergleicht kumulativ mit dem FULL-Tag derselben Releaselinie.
    base_reference = f"v{tag_match.group('releaselinie')}.{_FULL_RELEASE}"
    base_sha = git.resolve(repository_root, f"refs/tags/{base_reference}")
    git.require_ancestor(repository_root, base_sha, target_sha)
    return (base_reference, base_sha), git.changes(repository_root, base_sha, target_sha)


def project_elements(
    repository_root: str | Path,
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

    root = Path(repository_root)
    # FULL: alle Projektdateien als hinzugefügt melden.
    if base is None:
        return [
            ["A", path.relative_to(root / project).as_posix()]
            for path in sorted((root / project).rglob("*"))
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
                source = repository_root / repository_relative
                if not source.is_file():
                    raise DeliveryError(Status.PACKAGE_FAILED, "DELTA-Datei fehlt")
                destination = staging / repository_relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

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


# Öffentliche Paketerzeugung für Sync und Release.
def build_project_package(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    output_directory: str | Path,
    project: str,
    project_code: str,
    changes: Iterable[git.GitChange],
    base: tuple[str, str] | None,
    target: tuple[str, str],
) -> tuple[Path, ...]:
    """Erzeugt Archive und JSON-Informationsdatei für ein Projekt.

    `base` und `target` enthalten jeweils Referenz und Commit-SHA. Bei einem
    FULL entfällt `base`. Bei einem DELTA bestimmt `changes` die gemeinsame
    Elementliste für Archiv, Löschliste und Informationsdatei.
    """

    root = Path(repository_root)
    output = Path(output_directory)
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Paketausgabeverzeichnis kann nicht erstellt werden") from exc

    # Gemeinsame Elementliste für Archiv, Löschliste und Informationsdatei.
    elements = project_elements(root, project, base=base, changes=changes)

    prefix = f"{configuration.kuerzel}{project_code}"
    archives: list[Path] = []
    # FULL erhält zusätzlich das vollständige F-Archiv.
    if base is None:
        full_archive = output / f"{prefix}F.tgz"
        _write_archive(full_archive, root, [f"./{project}"])
        archives.append(full_archive)

    # D-Archiv entsteht immer. Bei FULL bleibt die Änderungsmenge leer.
    delta_archive = output / f"{prefix}D.tgz"
    _write_delta_archive(
        delta_archive,
        root,
        project,
        f"{prefix}D.txt",
        [] if base is None else elements,
    )
    archives.append(delta_archive)

    # Stand, Prüfsummen und Elementliste in der Informationsdatei ablegen.
    stand: dict[str, object] = {"bis": {"referenz": target[0], "commit": target[1]}}
    if base is not None:
        stand["von"] = {"referenz": base[0], "commit": base[1]}

    checksums = {archive.stem[-1]: _sha256(archive) for archive in archives}
    information = output / _INFORMATION_NAME.format(kuerzel=configuration.kuerzel, project=project)
    try:
        information.write_text(
            json.dumps(
                {
                    "projekt": project,
                    "stand": stand,
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

    return tuple(archives)
