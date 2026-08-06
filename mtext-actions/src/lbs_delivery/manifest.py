"""Schreibt und prüft das Manifest, das Releasemetadaten mit Artefaktdateien verbindet.

Beim Publish vergleicht die Prüfung die Paket- und Informationsdateien mit
Größe und Prüfsumme aus dem beim Releasebau geschriebenen Manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


def sha256_file(path: str | Path) -> str:
    """Berechnet die SHA-256-Prüfsumme zur Bindung einer Datei an das Manifest."""

    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    """Schreibt ein intern aufgebautes Manifest in stabiler und lesbarer Form."""

    target = Path(path)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_and_verify(
    manifest_path: str | Path, artifact_root: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Lädt ein Manifest und prüft alle Dateien aus dem Releasebau."""

    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist ungültig") from exc

    try:
        artifacts = manifest["artifacts"]
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist unvollständig") from exc
    if not isinstance(artifacts, list):
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist unvollständig")

    packages: list[dict[str, Any]] = []

    # Paket- und Informationsdateien gehören gemeinsam zur geprüften Lieferung.
    # Die Paketliste wird getrennt zurückgegeben, weil nur sie an den Mainframe geht.
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("kind") not in {"package", "information"}:
            raise DeliveryError(Status.PACKAGE_FAILED, "Releaseartefakt ist ungültig")

        try:
            relative_path = artifact["path"]
            expected_size = artifact["size"]
            expected_sha256 = artifact["sha256"]
        except KeyError as exc:
            raise DeliveryError(Status.PACKAGE_FAILED, "Releaseartefakt ist unvollständig") from exc
        if (
            not isinstance(relative_path, str)
            or not isinstance(expected_size, int)
            or not isinstance(expected_sha256, str)
        ):
            raise DeliveryError(Status.PACKAGE_FAILED, "Releaseartefakt ist ungültig")

        # Datei, Größe und Prüfsumme gegen das Manifest prüfen.
        path = Path(artifact_root) / relative_path
        if not path.is_file():
            raise DeliveryError(Status.PACKAGE_FAILED, f"Releaseartefakt fehlt: {relative_path}")

        size = path.stat().st_size
        if size != expected_size:
            raise DeliveryError(
                Status.PACKAGE_FAILED,
                f"Releaseartefakt hat falsche Größe: {relative_path} "
                f"(erwartet {expected_size}, gefunden {size})",
            )

        if sha256_file(path) != expected_sha256:
            raise DeliveryError(Status.PACKAGE_FAILED, f"Releaseartefakt hat falsche Prüfsumme: {relative_path}")

        if artifact["kind"] == "package":
            packages.append(artifact)

    # Mindestens ein Paket muss für die Mainframe-Übergabe vorliegen.
    if not packages:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest enthält kein Paket")

    return manifest, packages
