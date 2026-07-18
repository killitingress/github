"""Erzeugt reproduzierbare FULL- und kumulative DELTA-Lieferungen."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable

from .config import MandantConfig
from .delivery_names import project_code_for_name
from .errors import DeliveryError, Status
from .git_refs import GitChange, diff_name_status
from .manifest import sha256_file, write_manifest
from .paths import reject_symlinks, resolve_within


# Bewahrt die historische Kennzeichnung für ein Release ohne Vorgänger.
LEGACY_NO_PREVIOUS_RELEASE = "R001.100"
FULL_RELEASE_SUFFIX = ".100"
ARCHIVE_NAME_TEMPLATE = "{mandant}{project_code}{delivery_code}.tgz"
DELETION_LIST_NAME_TEMPLATE = "{mandant}{project_code}D.txt"
INFO_NAME_TEMPLATE = (
    "_INFO_{mandant}-{project}-{delivery_type}-{release}-{previous_release}.txt"
)


def release_type(tag: str) -> str:
    """Leitet aus der Tagendung den Lieferungstyp FULL oder DELTA ab."""

    return "FULL" if tag.endswith(FULL_RELEASE_SUFFIX) else "DELTA"


def base_tag(tag: str) -> str:
    """Ermittelt den `.100`-Basistag der Releaselinie."""

    return f"{tag[:4]}{FULL_RELEASE_SUFFIX}"


def _safe_source(root: Path, relative: str) -> Path:
    """Löst einen Ressourcenpfad sicher innerhalb des Repositorys auf."""

    return resolve_within(
        root,
        relative,
        status=Status.PACKAGE_FAILED,
        subject="resource",
        reject_symlink=True,
    )


def _all_paths(project_root: Path, repository_root: Path) -> list[str]:
    """Sammelt alle regulären Dateien und Verzeichnisse eines FULL-Projekts."""

    if not project_root.is_dir():
        raise DeliveryError(Status.PACKAGE_FAILED, "release project is missing")
    reject_symlinks(
        project_root, status=Status.PACKAGE_FAILED, subject="resource"
    )
    result = [project_root.relative_to(repository_root).as_posix()]
    for path in sorted(project_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir() or path.is_file():
            result.append(path.relative_to(repository_root).as_posix())
    return result


def _parent_directories(paths: Iterable[str], project_path: str) -> list[str]:
    """Ermittelt die für ein Archiv erforderlichen übergeordneten Verzeichnisse."""

    directories = {project_path}
    for value in paths:
        parent = PurePosixPath(value).parent
        while parent.as_posix() not in {".", ""}:
            directories.add(parent.as_posix())
            if parent.as_posix() == project_path:
                break
            parent = parent.parent
    return sorted(directories, key=lambda item: (len(PurePosixPath(item).parts), item))


def _tar_info(name: str, *, directory: bool, size: int = 0) -> tarfile.TarInfo:
    """Erzeugt normalisierte TAR-Metadaten für reproduzierbare Archive."""

    info = tarfile.TarInfo(name=name)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.size = 0 if directory else size
    info.mode = 0o755 if directory else 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _archive_name(path: str, dot_prefix: bool) -> str:
    """Übernimmt bei FULL die historische `./`-Präfixkonvention."""

    return f"./{path}" if dot_prefix else path


def create_archive(
    archive_path: str | Path,
    repository_root: str | Path,
    project_path: str,
    file_paths: Iterable[str],
    *,
    dot_prefix: bool,
    deletion_list_name: str | None = None,
    deletion_paths: Iterable[str] = (),
) -> list[str]:
    """Schreibt ein deterministisches TAR.GZ und liefert dessen logische Einträge."""

    root = Path(repository_root).resolve()
    files = sorted(set(file_paths))
    directories = _parent_directories(files, project_path)
    target = Path(archive_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    logical_names: list[str] = []
    try:
        with target.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with tarfile.open(
                    fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT
                ) as archive:
                    if deletion_list_name is not None:
                        deletion_content = "".join(
                            f"{path}\n" for path in sorted(set(deletion_paths))
                        ).encode("utf-8")
                        archive.addfile(
                            _tar_info(
                                deletion_list_name,
                                directory=False,
                                size=len(deletion_content),
                            ),
                            io.BytesIO(deletion_content),
                        )
                        logical_names.append(deletion_list_name)
                    for directory in directories:
                        name = _archive_name(directory, dot_prefix)
                        archive.addfile(_tar_info(name, directory=True))
                        logical_names.append(f"{name}/")
                    for relative in files:
                        source = _safe_source(root, relative)
                        if not source.is_file() or source.is_symlink():
                            raise DeliveryError(
                                Status.PACKAGE_FAILED, "release file is missing or unsafe"
                            )
                        data = source.read_bytes()
                        name = _archive_name(relative, dot_prefix)
                        archive.addfile(
                            _tar_info(name, directory=False, size=len(data)),
                            io.BytesIO(data),
                        )
                        logical_names.append(name)
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "cannot create release archive") from exc
    return logical_names


def _belongs(path: str, project_path: str) -> bool:
    """Prüft, ob ein Repositorypfad zu einem fachlichen Projekt gehört."""

    return path == project_path or path.startswith(f"{project_path}/")


def delta_paths(
    changes: Iterable[GitChange], project_path: str
) -> tuple[list[str], list[str]]:
    """Teilt kumulative Git-Änderungen in Paketinhalt und Löschliste auf."""

    included: set[str] = set()
    deleted: set[str] = set()
    for change in changes:
        if change.status in {"A", "M", "T"} and _belongs(change.path, project_path):
            included.add(change.path)
        elif change.status == "D" and _belongs(change.path, project_path):
            deleted.add(change.path)
        elif change.status in {"R", "C"}:
            if change.old_path and _belongs(change.old_path, project_path):
                deleted.add(change.old_path)
            if _belongs(change.path, project_path):
                included.add(change.path)
    return sorted(included), sorted(deleted)


def _change_lines(changes: Iterable[GitChange], project_path: str) -> list[str]:
    """Formatiert direkte Änderungen für die historische Informationsdatei."""

    lines: list[str] = []
    for change in changes:
        if change.status in {"R", "C"}:
            if change.old_path and _belongs(change.old_path, project_path):
                lines.append(f"D       VORRELEASE/{change.old_path}")
            if _belongs(change.path, project_path):
                lines.append(f"A       VORRELEASE/{change.path}")
        elif _belongs(change.path, project_path):
            lines.append(f"{change.status}       VORRELEASE/{change.path}")
    return lines


def _write_info(
    path: Path,
    *,
    mandant: str,
    project: str,
    delivery_type: str,
    release_tag: str,
    previous_tag: str,
    direct_changes: Iterable[GitChange],
    archive_names: Iterable[str],
) -> None:
    """Schreibt die fachlich erwartete Informationsdatei zu einem Projektpaket."""

    change_lines = _change_lines(direct_changes, project)
    lines = [
        f"Subject: Bereitstellung {mandant} - {project} - {delivery_type} - Release {release_tag}",
        "",
        (
            f"Folgende DIFFs wurden beim Vergleich zwischen {previous_tag} und "
            f"{release_tag} fuer Mandant {mandant} und das Projekt {project} in "
            f"der Lieferung vom Typ {delivery_type} erkannt:"
        ),
        "",
        *change_lines,
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
    repository_root: str | Path,
    output_directory: str | Path,
    mandant: MandantConfig,
    *,
    repository_name: str,
    release_tag: str,
    profile_name: str,
    target_sha: str,
    base_sha: str | None,
    previous_tag: str | None,
    previous_sha: str | None,
) -> Path:
    """Baut alle Projektpakete und das Manifest für einen geprüften Releasekontext."""

    root = Path(repository_root).resolve()
    output = Path(output_directory)
    if output.exists() and any(output.iterdir()):
        raise DeliveryError(Status.PACKAGE_FAILED, "release output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    delivery_type = release_type(release_tag)
    cumulative_changes: list[GitChange] = []
    if delivery_type == "DELTA":
        if base_sha is None:
            raise DeliveryError(Status.PACKAGE_FAILED, "DELTA base SHA is missing")
        cumulative_changes = diff_name_status(root, base_sha, target_sha)
    direct_changes: list[GitChange] = []
    if previous_sha is not None:
        direct_changes = diff_name_status(root, previous_sha, target_sha)
    previous_label = previous_tag or LEGACY_NO_PREVIOUS_RELEASE
    artifacts: list[dict[str, object]] = []
    for project in mandant["projects"]:
        project_name = project["name"]
        project_path = project["source_path"]
        project_code = project_code_for_name(project_name)
        delivery_code = "F" if delivery_type == "FULL" else "D"
        archive_name = ARCHIVE_NAME_TEMPLATE.format(
            mandant=mandant["code"],
            project_code=project_code,
            delivery_code=delivery_code,
        )
        deletion_name: str | None = None
        deletion_paths: list[str] = []
        if delivery_type == "FULL":
            all_paths = _all_paths(_safe_source(root, project_path), root)
            files = [path for path in all_paths if _safe_source(root, path).is_file()]
        else:
            files, deletion_paths = delta_paths(cumulative_changes, project_path)
            deletion_name = DELETION_LIST_NAME_TEMPLATE.format(
                mandant=mandant["code"], project_code=project_code
            )
        archive_path = output / archive_name
        logical_names = create_archive(
            archive_path,
            root,
            project_path,
            files,
            dot_prefix=delivery_type == "FULL",
            deletion_list_name=deletion_name,
            deletion_paths=deletion_paths,
        )
        info_name = INFO_NAME_TEMPLATE.format(
            mandant=mandant["code"],
            project=project_name,
            delivery_type=delivery_type,
            release=release_tag,
            previous_release=previous_label,
        )
        info_path = output / info_name
        _write_info(
            info_path,
            mandant=mandant["code"],
            project=project_name,
            delivery_type=delivery_type,
            release_tag=release_tag,
            previous_tag=previous_label,
            direct_changes=direct_changes,
            archive_names=logical_names,
        )
        member = f"{mandant['code']}{project_code}{delivery_code}"
        artifacts.append(
            {
                "kind": "package",
                "path": archive_path.name,
                "project": project_name,
                "size": archive_path.stat().st_size,
                "sha256": sha256_file(archive_path),
                "member": member,
                "project_code": project_code,
                "deletion_list": deletion_name,
                "deletion_count": len(deletion_paths),
            }
        )
        artifacts.append(
            {
                "kind": "information",
                "path": info_path.name,
                "project": project_name,
                "size": info_path.stat().st_size,
                "sha256": sha256_file(info_path),
            }
        )
    release_line = release_tag[:4]
    profile = mandant["handover_profiles"][profile_name]
    manifest = {
        "repository": repository_name,
        "mandant": mandant["code"],
        "release_tag": release_tag,
        "release_line": release_line,
        "delivery_type": delivery_type,
        "base_tag": base_tag(release_tag) if delivery_type == "DELTA" else None,
        "base_sha": base_sha,
        "target_sha": target_sha,
        "previous_tag": previous_tag,
        "previous_sha": previous_sha,
        "artifacts": artifacts,
        "jcl": {
            "ISPW": "P",
            # Die bestehende JCL nennt den fachlichen Stage-Code historisch LEVEL.
            "LEVEL": profile["stage"],
            "SUBSYS": mandant["subsystem"],
            "ASSIGNMENT": profile["assignment"],
        },
    }
    manifest_path = output / "manifest.json"
    write_manifest(manifest_path, manifest)
    return manifest_path
