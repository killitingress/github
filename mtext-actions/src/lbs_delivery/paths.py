"""Bündelt sichere Dateipfade, Symlinkprüfungen und Prüfsummen."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .errors import DeliveryError, Status


# Ein MiB begrenzt den Speicherbedarf beim Prüfen auch großer Lieferdateien.
SHA256_BLOCK_SIZE = 1024 * 1024


def sha256_file(path: str | Path) -> str:
    """Berechnet die SHA-256-Prüfsumme einer Datei blockweise."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(SHA256_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative_path(value: str, *, status: Status, subject: str) -> PurePosixPath:
    """Prüft einen relativen POSIX-Pfad auf Traversal und absolute Bestandteile."""

    # Die Prüfung erfolgt vor jeder Auflösung und schützt daher auch fehlende Ziele.
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise DeliveryError(status, f"unsicherer Pfad für {subject}")
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
    """Löst einen Pfad ausschließlich innerhalb der vorgegebenen Wurzel auf."""

    resolved_root = Path(root).resolve()
    relative = safe_relative_path(value, status=status, subject=subject)
    candidate = resolved_root.joinpath(*relative.parts)
    if reject_symlink and candidate.is_symlink():
        raise DeliveryError(status, f"Symlinks sind für {subject} nicht erlaubt")
    try:
        resolved = candidate.resolve(strict=strict)
    except OSError as exc:
        raise DeliveryError(status, f"Pfad für {subject} fehlt") from exc
    # Die Elternprüfung vermeidet Verwechslungen durch lediglich gleichnamige Präfixe.
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise DeliveryError(status, f"Pfad für {subject} verlässt seine Wurzel")
    return resolved


def reject_symlinks(path: str | Path, *, status: Status, subject: str) -> None:
    """Lehnt Symlinks in einer vollständigen Verzeichnisstruktur ab."""

    # Auch Symlinks unterhalb der Projektwurzel könnten aus dem erlaubten Baum führen.
    root = Path(path)
    if root.is_symlink():
        raise DeliveryError(status, f"Symlinks sind für {subject} nicht erlaubt")
    for item in root.rglob("*"):
        if item.is_symlink():
            raise DeliveryError(status, f"Symlinks sind für {subject} nicht erlaubt")
