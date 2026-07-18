"""Stellt Ressourcen isoliert bereit und veröffentlicht sie nach serverSync."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import DeliveryError, Status
from .paths import reject_symlinks, resolve_within


def stage_resources(
    source_root: str | Path,
    staging_root: str | Path,
    projects: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Kopiert geprüfte Projektstände in ein leeres laufbezogenes Staging."""

    # Ein frisches Staging verhindert die Übernahme von Resten eines älteren Laufs.
    source = Path(source_root).resolve()
    staging = Path(staging_root)
    if staging.exists() and any(staging.iterdir()):
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED, "Staging-Verzeichnis ist nicht leer"
        )
    staging.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for project in projects:
        project_source = resolve_within(
            source,
            project["source_path"],
            status=Status.VALIDATION_FAILED,
            subject="Ressourcenprojekt",
            reject_symlink=True,
        )
        if not project_source.is_dir():
            raise DeliveryError(
                Status.RESOURCE_TRANSFER_FAILED,
                f"Ressourcenprojekt fehlt: {project['name']}",
            )
        reject_symlinks(
            project_source, status=Status.VALIDATION_FAILED, subject="Ressource"
        )
        destination = staging / project["name"]
        shutil.copytree(project_source, destination, copy_function=shutil.copy2)
        staged.append(project["name"])
    return staged


def publish_server_sync(staging_root: str | Path, server_sync_root: str | Path) -> None:
    """Ersetzt Projektverzeichnisse nach expliziter Freigabe möglichst atomar."""

    staging = Path(staging_root).resolve()
    target_root = Path(server_sync_root)
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        for project in sorted(item for item in staging.iterdir() if item.is_dir()):
            temporary = target_root / f".{project.name}.new-{uuid.uuid4().hex}"
            backup = target_root / f".{project.name}.old-{uuid.uuid4().hex}"
            destination = target_root / project.name
            shutil.copytree(project, temporary, copy_function=shutil.copy2)
            had_destination = destination.exists()
            if had_destination:
                os.replace(destination, backup)
            # Das Backup stellt den letzten vollständigen Stand bei
            # Rename-Fehlern wieder her.
            try:
                os.replace(temporary, destination)
            except OSError:
                if had_destination and backup.exists():
                    os.replace(backup, destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED,
            "serverSync-Veröffentlichung fehlgeschlagen",
        ) from exc
