"""Schreibt und prüft das Manifest, das Releasemetadaten mit Artefaktdateien verbindet.

Beim Publish vergleicht die Prüfung die Paketdateien mit Größe und Prüfsumme aus
dem beim Releasebau geschriebenen Manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .process import DeliveryError, Status


def sha256_file(path: str | Path) -> str:
    """Berechnet die SHA-256-Prüfsumme zur Bindung einer Datei an das Manifest.

    Die Verarbeitung über die Standardbibliothek lädt Releasepakete nicht
    vollständig in den Speicher. Erzeugung und Prüfung verwenden dadurch
    dieselbe Prüfsummenberechnung.
    """

    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> Path:
    """Schreibt ein intern aufgebautes Manifest in stabiler und lesbarer Form.

    Sortierte Schlüssel und ein abschließender Zeilenumbruch machen die Datei
    reproduzierbar und in den Workflow-Artefakten leicht prüfbar.
    """

    target = Path(path)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_and_verify(
    manifest_path: str | Path, artifact_root: str | Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Lädt ein Manifest und prüft, ob die Paketdateien noch zum Releasebau passen.

    Beim Publish liegt das Manifest als Protokoll des Releasebaus vor. Größe und
    Prüfsumme jedes Pakets werden gegen die Dateien im Artefaktverzeichnis
    gehalten, damit veränderte oder beschädigte Dateien vor der Übergabe
    auffallen.
    """

    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        artifacts = manifest["artifacts"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest ist ungültig") from exc

    root = Path(artifact_root)
    packages: list[dict[str, Any]] = []
    for artifact in artifacts:
        if artifact.get("kind") != "package":
            continue
        try:
            path = root / artifact["path"]
            if path.stat().st_size != artifact["size"] or sha256_file(path) != artifact["sha256"]:
                raise ValueError
            packages.append(artifact)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise DeliveryError(Status.PACKAGE_FAILED, "Releaseartefakt ist ungültig") from exc
    if not packages:
        raise DeliveryError(Status.PACKAGE_FAILED, "Manifest enthält kein Paket")
    return manifest, packages
