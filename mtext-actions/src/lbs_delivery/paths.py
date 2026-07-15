"""Bündelt kanonische Pfad- und Symlinkprüfungen innerhalb fester Wurzeln."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .errors import DeliveryError, Status


def safe_relative_path(value: str, *, status: Status, subject: str) -> PurePosixPath:
    """Prüft einen relativen POSIX-Pfad auf Traversal und absolute Bestandteile."""

    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise DeliveryError(status, f"unsafe {subject} path")
    return path


def resolve_within(
    root: str | Path,
    value: str,
    *,
    status: Status,
    subject: str,
    strict: bool = False,
    reject_symlink: bool = False,
) -> Path:
    """Löst einen Pfad nur dann auf, wenn er innerhalb der vorgegebenen Wurzel bleibt."""

    resolved_root = Path(root).resolve()
    relative = safe_relative_path(value, status=status, subject=subject)
    candidate = resolved_root.joinpath(*relative.parts)
    if reject_symlink and candidate.is_symlink():
        raise DeliveryError(status, f"{subject} symlinks are not allowed")
    try:
        resolved = candidate.resolve(strict=strict)
    except OSError as exc:
        raise DeliveryError(status, f"{subject} path is missing") from exc
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise DeliveryError(status, f"{subject} path escapes its root")
    return resolved


def reject_symlinks(path: str | Path, *, status: Status, subject: str) -> None:
    """Lehnt Symlinks in einer vollständigen Verzeichnisstruktur ab."""

    root = Path(path)
    if root.is_symlink():
        raise DeliveryError(status, f"{subject} symlinks are not allowed")
    for item in root.rglob("*"):
        if item.is_symlink():
            raise DeliveryError(status, f"{subject} symlinks are not allowed")
