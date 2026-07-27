"""Synchronisiert einen geprüften Repositorystand mit den externen M/Text-Systemen.

Der Ablauf stellt die Projektverzeichnisse bereit, ersetzt ihre serverSync-Ziele
mit Rückfallmöglichkeit und ruft den zur Releaselinie und Umgebung des
Quellbranches gehörenden Adapter auf.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .process import DeliveryError, Status
from .config import Configuration
from .git import require_checkout


# Jede Synchronisationsumgebung liefert die Endungen für ihr serverSync-Verzeichnis
# und ihren Adapterhost.
SYNC_STAGES = {"Entwicklung": ("E", "e"), "Abnahme": ("A", "a")}

# Antworttexte des Adapters werden auf ein MiB begrenzt. So kann eine unerwartete
# Gegenstelle beim Sammeln der Diagnose nicht unbegrenzt Runner-Speicher belegen.
ADAPTER_RESPONSE_LIMIT = 1024 * 1024  # 1 MB

# Eine blockierte Adapterverbindung darf den Workflow höchstens eine Minute
# aufhalten, bevor die Synchronisation als fehlgeschlagen gilt.
ADAPTER_TIMEOUT = 60.0


def publish_server_sync(staging_root: str | Path, target_root: str | Path) -> None:
    """Ersetzt bereitgestellte Projekte unter serverSync mit Rückfallmöglichkeit.

    Jeder neue Verzeichnisbaum wird neben sein Ziel kopiert und anschließend
    eingewechselt. Scheitert dieser Wechsel nach dem Verschieben des alten
    Verzeichnisses, wird dessen Sicherung vor der Fehlermeldung wiederhergestellt.
    """

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
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "serverSync-Veröffentlichung fehlgeschlagen") from exc


def call_adapter(url: str, *, timeout: float) -> tuple[int, str]:
    """Ruft den M/Text-Adapter auf und gibt seine erfolgreiche HTTP-Antwort zurück.

    An dieser externen Grenze werden Transportfehler, nicht erfolgreiche
    Statuscodes und begrenzt gelesene Antworttexte in das Lieferfehlermodell
    übersetzt.
    """

    request = urllib.request.Request(
        url,
        # Der Adaptervertrag verlangt diese festen technischen Kennungen in
        # jeder Synchronisationsanfrage.
        data=json.dumps({"mandant": "MAN", "institut": "INR"}, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(ADAPTER_RESPONSE_LIMIT).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(ADAPTER_RESPONSE_LIMIT).decode("utf-8", errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter-Transport fehlgeschlagen") from exc
    if not 200 <= status < 300:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}")
    return status, body


def sync_resources(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    source_branch: str,
    staging_root: str | Path,
) -> dict[str, object]:
    """Prüft den angeforderten Quellstand und führt die vollständige Synchronisation aus.

    Die Branchstruktur bestimmt eine konfigurierte Releaselinie und Umgebung.
    Erst nach dem Nachweis des erreichbaren Checkouts werden die Projektverzeichnisse
    bereitgestellt, veröffentlicht und dem zugehörigen Adapter gemeldet.
    """

    releaselinie, _, environment = source_branch.partition("/")
    if environment not in SYNC_STAGES:
        raise DeliveryError(Status.VALIDATION_FAILED, "Zielumgebung ist ungültig")
    if source_branch != f"{releaselinie}/{environment}":
        raise DeliveryError(Status.VALIDATION_FAILED, "Branch passt nicht zur Zielumgebung")
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    require_checkout(repository_root, commit, source_branch)

    source_root = Path(repository_root)
    staging = Path(staging_root)
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for project in configuration.projects:
            shutil.copytree(source_root / project, staging / project, copy_function=shutil.copy2)
    except (OSError, shutil.Error) as exc:
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "Ressourcen-Staging fehlgeschlagen") from exc

    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    path_suffix, host_suffix = SYNC_STAGES[environment]
    publish_server_sync(staging_root, f"/nfs/mtext/{etaps_linie}{path_suffix}/serverSync")
    adapter_url = f"https://{etaps_linie}{host_suffix}.ltoma.intern/vMtextAdapter/sync"
    status, body = call_adapter(adapter_url, timeout=ADAPTER_TIMEOUT)
    return {"status": Status.ADAPTER_ACCEPTED.value, "http_status": status, "response_body": body}
