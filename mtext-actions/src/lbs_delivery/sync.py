"""Stellt Projektpakete für den M/Text-Adapter auf CIFS bereit.

Der Workflow erzeugt je betroffenem Projekt das gemeinsame F- oder D-Paket.
Er meldet dem Adapter das vollständig geschriebene Übergabeverzeichnis. Der
Adapter übernimmt die Pakete nach `serverSync` und startet die
M/Text-Synchronisation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .config import Configuration
from .git import changes, project_changes, require_ancestor, resolve
from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_package import build_project_package


# Vom Adapter werden höchstens 1 MB Antworttext eingelesen.
ADAPTER_RESPONSE_LIMIT = 1024 * 1024

# URL-Muster des LTOMA-Sync-Endpunktes.
ADAPTER_SYNC_URL = "https://{umgebung}.ltoma.intern/vMtextAdapter/sync"

# Diese Umgebungsvariable bezeichnet den auf dem Runner eingehängten
# CIFS-Basispfad für vollständige Übergabeaufträge.
CIFS_ROOT_ENVIRONMENT = "MTEXT_CIFS_ROOT"


def call_adapter(url: str, payload: dict[str, object]) -> tuple[int, str]:
    """Meldet dem Adapter ein vollständig bereitgestelltes CIFS-Verzeichnis."""

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            status = response.status
            body = response.read(ADAPTER_RESPONSE_LIMIT).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(ADAPTER_RESPONSE_LIMIT).decode(errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter ist nicht erreichbar") from exc
    if not 200 <= status < 300:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}")
    return status, body


def sync_resources(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    previous_commit: str | None,
    source_branch: str,
    releaselinie: str,
    zielstufe: str,
    handoff_root: str | Path | None = None,
) -> dict[str, object]:
    """Erzeugt Projektpakete auf CIFS und meldet sie dem M/Text-Adapter.

    Ein normaler Push verwendet ausschließlich den Git-Vergleich zwischen
    `previous_commit` und `commit`. Ein Push ohne Vorgänger erzeugt für jedes
    Projekt ein FULL.
    """

    if zielstufe not in configuration.mtext_ziel_prefixe:
        raise DeliveryError(Status.VALIDATION_FAILED, "M/Text-Zielstufe ist ungültig")
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    if resolve(repository_root, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    require_ancestor(repository_root, commit, f"refs/remotes/origin/{source_branch}")

    git_changes = [] if previous_commit is None else changes(repository_root, previous_commit, commit)
    projects = [
        (project, project_code)
        for project, project_code in configuration.projects.items()
        if previous_commit is None or any(project_changes(git_changes, project))
    ]
    if not projects:
        return {"status": Status.ADAPTER_ACCEPTED.value, "projekte": []}

    if handoff_root is None:
        configured_root = os.environ.get(CIFS_ROOT_ENVIRONMENT)
        if not configured_root:
            raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabepfad ist nicht konfiguriert")
        handoff_root = configured_root

    root = Path(handoff_root)
    if not root.is_dir():
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabepfad ist nicht erreichbar")

    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    umgebung = f"{configuration.mtext_ziel_prefixe[zielstufe]}{etaps_linie}"
    environment_root = root / umgebung

    # Derselbe fachliche Auftrag erhält bei einem Wiederanlauf dieselbe ID.
    # Der Adapter verwendet sie unabhängig vom jeweils neuen CIFS-Verzeichnis
    # zur idempotenten Annahme.
    auftrag_document = {
        "mandant": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": releaselinie,
        "zielstufe": zielstufe,
        "branch": source_branch,
        "bis": commit,
        "projekte": [project for project, _ in projects],
    }
    if previous_commit is not None:
        auftrag_document["von"] = previous_commit
    auftrag = hashlib.sha256(
        json.dumps(auftrag_document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request_name = f"{configuration.kuerzel}-{commit[:12]}-{uuid.uuid4().hex}"
    request_path = environment_root / request_name

    try:
        request_path.mkdir(parents=True)
        for project, project_code in projects:
            build_project_package(
                configuration,
                repository_root=repository_root,
                output_directory=request_path,
                project=project,
                project_code=project_code,
                changes=git_changes,
                base=None if previous_commit is None else (source_branch, previous_commit),
                target=(source_branch, commit),
            )
    except (OSError, DeliveryError) as exc:
        shutil.rmtree(request_path, ignore_errors=True)
        if isinstance(exc, DeliveryError):
            raise
        raise DeliveryError(Status.RESOURCE_TRANSFER_FAILED, "CIFS-Übergabe ist fehlgeschlagen") from exc

    adapter_url = ADAPTER_SYNC_URL.format(umgebung=umgebung)
    payload = {
        "auftrag": auftrag,
        **auftrag_document,
        "pfad": str(request_path),
    }
    status, body = call_adapter(adapter_url, payload)

    return {
        "status": Status.ADAPTER_ACCEPTED.value,
        "http_status": status,
        "response_body": body,
        "pfad": str(request_path),
        "projekte": payload["projekte"],
    }
