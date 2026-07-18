"""Schreibt den Releasebeleg und prüft seine Dateien vor der Übergabe."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import DeliveryError, Status


# JSON-Objekte bleiben bis zur einmaligen Publish-Prüfung bewusst untypisiert.
Manifest = dict[str, Any]
# Ein Paket ist ein geprüfter Artefakteintrag mit Mainframe-Member.
Package = dict[str, Any]


def sha256_file(path: str | Path) -> str:
    """Berechnet den SHA-256 einer Datei mit der Standardbibliothek."""

    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_manifest(path: str | Path, manifest: Manifest) -> Path:
    """Schreibt das intern erzeugte Manifest ohne erneute Selbstvalidierung."""

    target = Path(path)
    target.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_and_verify(
    manifest_path: str | Path, artifact_root: str | Path
) -> tuple[Manifest, list[Package]]:
    """Lädt ein Manifest und prüft alle Dateien vor externen Wirkungen."""

    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        artifacts = manifest["artifacts"]
        jcl = manifest["jcl"]
        if not isinstance(manifest, dict) or not isinstance(artifacts, list):
            raise TypeError
        if not isinstance(jcl, dict) or not artifacts:
            raise TypeError
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist ungültig") from exc

    root = Path(artifact_root).resolve()
    packages: list[Package] = []
    for artifact in artifacts:
        try:
            kind = artifact["kind"]
            name = artifact["path"]
            size = artifact["size"]
            checksum = artifact["sha256"]
            if (
                kind not in ("package", "information")
                or not isinstance(name, str)
                or type(size) is not int
                or not isinstance(checksum, str)
            ):
                raise TypeError
            candidate = root / name
            if candidate.is_symlink():
                raise ValueError
            resolved = candidate.resolve(strict=True)
            if resolved.parent != root or not resolved.is_file():
                raise ValueError
            if resolved.stat().st_size != size or sha256_file(resolved) != checksum:
                raise ValueError
            if kind == "package":
                if not isinstance(artifact.get("member"), str):
                    raise TypeError
                packages.append(artifact)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise DeliveryError(
                Status.PACKAGE_FAILED, "Releaseartefakt ist ungültig"
            ) from exc
    if not packages:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest enthält kein Paket")
    return manifest, packages
