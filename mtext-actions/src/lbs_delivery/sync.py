"""Synchronisiert einen geprüften Repositorystand nach M/Text."""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

from .config import ADAPTER_PAYLOAD, SYNC_STAGES, Configuration
from .errors import DeliveryError, Status
from .git import require_checkout


# Obergrenze für den gelesenen Adapter-Antwortkörper in Bytes; verhindert unbeschränkten Speicherverbrauch.
ADAPTER_RESPONSE_LIMIT = 1024 * 1024 # 1 MB


def stage_projects(
    repository_root: str | Path,
    staging_root: str | Path,
    projects: list[str],
) -> list[str]:
    """Kapselt die Symlink-Prüfung und Kopie an der Staging-Systemgrenze."""

    source_root = Path(repository_root)
    staging = Path(staging_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for project in projects:
            source = source_root / project
            if not source.is_dir() or source.is_symlink():
                raise DeliveryError(
                    Status.RESOURCE_TRANSFER_FAILED,
                    f"Ressourcenprojekt fehlt: {project}",
                )
            if any(item.is_symlink() for item in source.rglob("*")):
                raise DeliveryError(
                    Status.VALIDATION_FAILED, "Ressourcen enthalten einen Symlink"
                )
            shutil.copytree(source, staging / project, copy_function=shutil.copy2)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED, "Ressourcen-Staging fehlgeschlagen"
        ) from exc
    return projects


def publish_server_sync(staging_root: str | Path, target_root: str | Path) -> None:
    """Kapselt die wiederherstellbare Ersetzung am externen serverSync-Ziel."""

    staging = Path(staging_root)
    target = Path(target_root)
    try:
        target.mkdir(parents=True, exist_ok=True)
        for project in sorted(item for item in staging.iterdir() if item.is_dir()):
            destination = target / project.name
            temporary = target / f".{project.name}.new-{uuid.uuid4().hex}"
            backup = target / f".{project.name}.old-{uuid.uuid4().hex}"
            shutil.copytree(project, temporary, copy_function=shutil.copy2)
            if destination.exists():
                os.replace(destination, backup)
            try:
                os.replace(temporary, destination)
            except OSError:
                if backup.exists():
                    os.replace(backup, destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(
            Status.RESOURCE_TRANSFER_FAILED,
            "serverSync-Veröffentlichung fehlgeschlagen",
        ) from exc


def call_adapter(
    url: str,
    *,
    timeout: float,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[int, str]:
    """Kapselt den HTTP-Aufruf des M/Text-Adapters als externe Systemgrenze."""

    request = urllib.request.Request(
        url,
        data=json.dumps(ADAPTER_PAYLOAD, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(ADAPTER_RESPONSE_LIMIT).decode(
                "utf-8", errors="replace"
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(ADAPTER_RESPONSE_LIMIT).decode("utf-8", errors="replace")
        raise DeliveryError(
            Status.ADAPTER_FAILED,
            f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}",
        ) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(
            Status.ADAPTER_FAILED, "Adapter-Transport fehlgeschlagen"
        ) from exc
    if not 200 <= status < 300:
        raise DeliveryError(
            Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}"
        )
    return status, body


def sync_resources(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    source_branch: str,
    environment: str,
    staging_root: str | Path,
    timeout: float,
    execute: bool,
) -> dict[str, object]:
    """Führt Prüfung, Staging und optional die externe Synchronisation aus."""

    releaselinie = source_branch.partition("/")[0]
    if (
        environment not in SYNC_STAGES
        or source_branch != f"{releaselinie}/{environment}"
        or releaselinie not in configuration.releaselinien
    ):
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "Branch und Zielumgebung passen nicht zusammen",
        )
    require_checkout(repository_root, commit, source_branch)
    projects = stage_projects(
        repository_root, staging_root, list(configuration.projects)
    )
    if not execute:
        return {"status": Status.ARTIFACT_READY.value, "projects": projects}

    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    path_suffix, host_suffix = SYNC_STAGES[environment]
    publish_server_sync(
        staging_root, f"/nfs/mtext/{etaps_linie}{path_suffix}/serverSync"
    )
    status, body = call_adapter(
        f"https://{etaps_linie}{host_suffix}.ltoma.intern/vMtextAdapter/sync",
        timeout=timeout,
    )
    return {
        "status": Status.ADAPTER_ACCEPTED.value,
        "http_status": status,
        "response_body": body,
    }
