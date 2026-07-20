"""Erzeugt FULL- und kumulative DELTA-Lieferungen aus einem Release-Tag."""

from __future__ import annotations

import gzip
import shutil
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from .config import Configuration
from .errors import DeliveryError, Status
from .git import (
    GitChange,
    changes,
    previous_tag,
    require_ancestor,
    require_release_tag,
    resolve,
)
from .manifest import Manifest, sha256_file, write_manifest


# Ohne echten Vorgänger verwendet der bestehende Informationsvertrag diesen Wert.
LEGACY_PREVIOUS_TAG = "R001.100"
# Die Endung `.100` kennzeichnet den vollständigen Stand einer Releaselinie.
FULL_SUFFIX = ".100"
# Archivnamen bestehen aus Mandantenkürzel, Projektcode und Lieferart.
ARCHIVE_NAME = "{mandant}{projektcode}{delivery_code}.tgz"
# Jede DELTA-Lieferung enthält eine historisch benannte Löschliste.
DELETION_NAME = "{mandant}{projektcode}D.txt"
# Informationsdateien dokumentieren Projekt, Lieferart und verglichene Tags.
INFORMATION_NAME = (
    "_INFO_{mandant}-{project}-{delivery_type}-{tag}-{previous_tag}.txt"
)


def _normalize_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Entfernt lokale Dateimetadaten aus einem reproduzierbaren Archiv."""

    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if info.isdir() else 0o644
    return info


def _write_archive(
    archive_path: Path, entries: Iterable[tuple[Path, str]]
) -> list[str]:
    """Schreibt vorbereitete Dateien und Verzeichnisse in ein bytegleiches TAR.GZ."""

    try:
        with archive_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with tarfile.open(
                    fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT
                ) as archive:
                    for source, name in entries:
                        archive.add(
                            source,
                            arcname=name,
                            recursive=True,
                            filter=_normalize_tar_info,
                        )
                    return archive.getnames()
    except (OSError, tarfile.TarError) as exc:
        raise DeliveryError(
            Status.PACKAGE_FAILED, "Releasearchiv kann nicht erzeugt werden"
        ) from exc


def _project_changes(
    git_changes: Iterable[GitChange], project: str
) -> Iterator[tuple[str, str]]:
    """Projiziert Git-Status einmalig auf fachliche Projektänderungen."""

    prefix = f"{project}/"
    for change in git_changes:
        if change.status == "R":
            projected = (("D", change.old_path), ("A", change.path))
        elif change.status == "C":
            projected = (("A", change.path),)
        else:
            projected = ((change.status, change.path),)
        for status, path in projected:
            if path is not None and (path == project or path.startswith(prefix)):
                yield status, path


def _delta_paths(
    git_changes: Iterable[GitChange], project: str
) -> tuple[list[str], list[str]]:
    """Teilt den kumulativen Git-Diff in Paketinhalt und Löschliste."""

    included: set[str] = set()
    deleted: set[str] = set()
    for status, path in _project_changes(git_changes, project):
        if status in {"A", "M", "T"}:
            included.add(path)
        elif status == "D":
            deleted.add(path)
    return sorted(included), sorted(deleted)


def _delta_archive(
    archive_path: Path,
    repository_root: Path,
    project: str,
    included: list[str],
    deleted: list[str],
    deletion_name: str,
) -> list[str]:
    """Baut den DELTA-Verzeichnisstand und archiviert ihn wie der Jenkins-Hook."""

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        (staging / project).mkdir(parents=True)
        for relative in included:
            source = repository_root / relative
            if not source.is_file() or source.is_symlink():
                raise DeliveryError(
                    Status.PACKAGE_FAILED, "DELTA-Datei fehlt oder ist ein Symlink"
                )
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (staging / deletion_name).write_text(
            "".join(f"{path}\n" for path in deleted), encoding="utf-8"
        )
        entries = [(item, item.name) for item in sorted(staging.iterdir())]
        return _write_archive(archive_path, entries)


def _info_lines(git_changes: Iterable[GitChange], project: str) -> list[str]:
    """Formatiert den direkten Vorgängervergleich für die Informationsdatei."""

    return [
        f"{status}       VORRELEASE/{path}"
        for status, path in _project_changes(git_changes, project)
    ]


def _write_information(
    path: Path,
    *,
    mandant: str,
    project: str,
    delivery_type: str,
    tag: str,
    previous: str,
    git_changes: Iterable[GitChange],
    archive_names: Iterable[str],
) -> None:
    """Schreibt den bestehenden lesbaren Releasebeleg eines Projektpakets."""

    lines = [
        (
            f"Subject: Bereitstellung {mandant} - {project} - "
            f"{delivery_type} - Release {tag}"
        ),
        "",
        (
            f"Folgende DIFFs wurden beim Vergleich zwischen {previous} und {tag} "
            f"fuer Mandant {mandant} und das Projekt {project} in der Lieferung "
            f"vom Typ {delivery_type} erkannt:"
        ),
        "",
        *_info_lines(git_changes, project),
        "",
        "",
        (
            f"Folgender Inhalt ist im TAR-Archiv fuer Mandant {mandant} und das "
            f"Projekt {project} in der Lieferung vom Typ {delivery_type} enthalten:"
        ),
        "",
        *archive_names,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_release(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    output_directory: str | Path,
    repository_name: str,
    tag: str,
    trigger_sha: str,
) -> Path:
    """Prüft den Releasebezug und erzeugt alle Lieferdateien in einem Ablauf."""

    root = Path(repository_root)
    releaselinie = tag[:4]
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    target_sha = require_release_tag(
        root, tag, f"{releaselinie}/Bereitstellung"
    )
    if trigger_sha and trigger_sha != target_sha:
        raise DeliveryError(
            Status.SOURCE_FAILED, "auslösender Commit stimmt nicht zum Tag"
        )

    delivery_type = "FULL" if tag.endswith(FULL_SUFFIX) else "DELTA"
    base = f"{releaselinie}{FULL_SUFFIX}" if delivery_type == "DELTA" else None
    base_sha = resolve(root, f"refs/tags/{base}") if base else None
    if base_sha:
        require_ancestor(root, base_sha, target_sha)
    previous = previous_tag(root, tag)
    previous_sha = resolve(root, f"refs/tags/{previous}") if previous else None
    cumulative = changes(root, base_sha, target_sha) if base_sha else []
    direct = changes(root, previous_sha, target_sha) if previous_sha else []

    output = Path(output_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise DeliveryError(
            Status.PACKAGE_FAILED, "Release-Ausgabeverzeichnis ist nicht neu"
        ) from exc

    artifacts: list[dict[str, object]] = []
    previous_label = previous or LEGACY_PREVIOUS_TAG
    for project, projektcode in configuration.projects.items():
        delivery_code = "F" if delivery_type == "FULL" else "D"
        archive_path = output / ARCHIVE_NAME.format(
            mandant=configuration.kuerzel,
            projektcode=projektcode,
            delivery_code=delivery_code,
        )
        packages = [(archive_path, delivery_code)]
        if delivery_type == "FULL":
            source = root / project
            if not source.is_dir() or source.is_symlink():
                raise DeliveryError(Status.PACKAGE_FAILED, "Releaseprojekt fehlt")
            if any(item.is_symlink() for item in source.rglob("*")):
                raise DeliveryError(
                    Status.PACKAGE_FAILED, "Releaseprojekt enthält einen Symlink"
                )
            archive_names = _write_archive(
                archive_path, [(source, f"./{project}")]
            )
            deletion_name = DELETION_NAME.format(
                mandant=configuration.kuerzel, projektcode=projektcode
            )
            delta_path = output / ARCHIVE_NAME.format(
                mandant=configuration.kuerzel,
                projektcode=projektcode,
                delivery_code="D",
            )
            # Das bei FULL zusätzlich erzeugte leere D-Paket gehört zum
            # bestehenden Mainframe-Übergabevertrag.
            _delta_archive(delta_path, root, project, [], [], deletion_name)
            packages.append((delta_path, "D"))
        else:
            included, deleted = _delta_paths(cumulative, project)
            deletion_name = DELETION_NAME.format(
                mandant=configuration.kuerzel, projektcode=projektcode
            )
            archive_names = _delta_archive(
                archive_path,
                root,
                project,
                included,
                deleted,
                deletion_name,
            )

        information_path = output / INFORMATION_NAME.format(
            mandant=configuration.kuerzel,
            project=project,
            delivery_type=delivery_type,
            tag=tag,
            previous_tag=previous_label,
        )
        _write_information(
            information_path,
            mandant=configuration.kuerzel,
            project=project,
            delivery_type=delivery_type,
            tag=tag,
            previous=previous_label,
            git_changes=direct,
            archive_names=archive_names,
        )
        for package_path, package_code in packages:
            artifacts.append(
                {
                    "kind": "package",
                    "path": package_path.name,
                    "project": project,
                    "member": (
                        f"{configuration.kuerzel}{projektcode}{package_code}"
                    ),
                    "size": package_path.stat().st_size,
                    "sha256": sha256_file(package_path),
                }
            )
        artifacts.append(
            {
                "kind": "information",
                "path": information_path.name,
                "project": project,
                "size": information_path.stat().st_size,
                "sha256": sha256_file(information_path),
            }
        )

    hostprofil_name = configuration.releaselinien[releaselinie]["hostprofil"]
    hostprofil = configuration.hostprofile[hostprofil_name]
    manifest: Manifest = {
        "repository": repository_name,
        "mandant": configuration.kuerzel,
        "release_tag": tag,
        "delivery_type": delivery_type,
        "base_tag": base,
        "target_sha": target_sha,
        "previous_tag": previous,
        "artifacts": artifacts,
        "jcl": {
            "ISPW": configuration.ispw,
            "LEVEL": hostprofil["stage"],
            "SUBSYS": configuration.subsystem,
            "ASSIGNMENT": hostprofil["assignment"],
        },
    }
    return write_manifest(output / "manifest.json", manifest)
