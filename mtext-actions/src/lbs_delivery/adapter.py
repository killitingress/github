"""Spricht den M/Text-Adapter per HTTPS an.

Der Sync-Workflow legt hier einen Auftrag an, lädt dessen Archive hoch und
fragt den Verarbeitungsstatus ab. Dieses Modul kapselt den Adaptervertrag und
die HTTP-Grenze zur LTOMA-Umgebung.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from typing import Literal

from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_artifacts import ProjectArtifacts


# Begrenzt gelesene Adapterantworten, damit fehlerhafte Antworten nicht den
# Arbeitsspeicher vollständig belegen.
_RESPONSE_LIMIT = 1024 * 1024

# Blockgröße beim Streaming großer Archive zum Adapter.
_UPLOAD_BLOCK_SIZE = 1024 * 1024

# Abstand zwischen Statusabfragen, solange der Adapter noch verarbeitet.
_POLL_INTERVAL_SECONDS = 5

# Auftragszustände, in denen der Adapter noch arbeitet oder Dateien erwartet.
_ACTIVE_STATUSES = frozenset({"ready", "uploading", "processing"})

# Auftragszustände, die die Verarbeitung beim Adapter beenden.
_TERMINAL_STATUSES = frozenset({"succeeded", "failed"})

# URL-Muster der Adapter-Synchronisation. `{umgebung}` setzt sich aus
# M/Text-Zielstufen-Prefix und ETAPS-Linie zusammen.
_SYNC_URL = "https://{umgebung}.ltoma.intern/vMtextAdapter/sync"


def synchronize(
    target_prefix: str,
    etaps_linie: str,
    *,
    kuerzel: str,
    artifacts: Iterator[tuple[str, ProjectArtifacts]],
    idempotency_key: str,
) -> dict[str, object]:
    """Führt einen Adapterauftrag von der Anlage bis zum Endstatus und Löschen aus.

    Die Informationen zu allen Archiven werden beim Anlegen übertragen.
    Danach folgt ein PUT mit den unveränderten Bytes je F- oder D-Archiv.
    """

    prepared_artifacts = list(artifacts)
    full = {project_artifacts.f_archiv is not None for _project, project_artifacts in prepared_artifacts}
    if len(full) != 1:
        raise DeliveryError(Status.ADAPTER_FAILED, "Archive des Auftrags haben unterschiedliche Auftragsarten")

    auftragsart = "FULL" if full.pop() else "DELTA"
    archive_uploads: list[tuple[Path, dict[str, object]]] = []
    for _project, project_artifacts in prepared_artifacts:
        archive = project_artifacts.f_archiv if auftragsart == "FULL" else project_artifacts.d_archiv
        if archive is None:
            raise DeliveryError(Status.ADAPTER_FAILED, "Zur Auftragsart fehlt ein passendes Archiv")
        try:
            information = json.loads(project_artifacts.information.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryError(Status.ADAPTER_FAILED, "Informationsdatei kann nicht gelesen werden") from exc
        if not isinstance(information, dict):
            raise DeliveryError(Status.ADAPTER_FAILED, "Informationsdatei ist ungültig")
        archive_uploads.append((archive, information))

    adapter_url = _SYNC_URL.format(umgebung=f"{target_prefix}{etaps_linie}")
    created = _call_adapter(
        "POST",
        adapter_url,
        {
            "kuerzel": kuerzel,
            "auftragsart": auftragsart,
            "archive": [
                {"name": archive.name, "information": information}
                for archive, information in archive_uploads
            ],
        },
        {"Idempotency-Key": idempotency_key},
    )
    auftrag_id = created["auftrag_id"]
    auftrag_url = f"{adapter_url}/{urllib.parse.quote(auftrag_id, safe='')}"
    result = created

    if created["status"] in {"ready", "uploading"}:
        for archive, _information in archive_uploads:
            result = _upload_archive(auftrag_url, archive)
            if result["status"] in _TERMINAL_STATUSES:
                break

    # Der Workflow begrenzt Upload und Warten gemeinsam auf 30 Minuten.
    while result["status"] not in _TERMINAL_STATUSES:
        result = _call_adapter("GET", auftrag_url)
        if result["status"] in _ACTIVE_STATUSES:
            time.sleep(_POLL_INTERVAL_SECONDS)

    # Auftrag entfernen, ohne eine M/Text-Fehlermeldung zu überschreiben.
    message = result.get("meldung") or "M/Text-Synchronisation ist fehlgeschlagen"
    try:
        _call_adapter("DELETE", auftrag_url)
    except DeliveryError as exc:
        if result["status"] == "failed":
            raise DeliveryError(
                Status.ADAPTER_FAILED,
                f"{message}. Auftrag konnte nicht entfernt werden: {exc.args[0]}",
            ) from exc
        raise

    if result["status"] == "failed":
        raise DeliveryError(Status.ADAPTER_FAILED, message)

    return {"auftrag_id": auftrag_id} | (
        {"ergebnis": result["ergebnis"]} if "ergebnis" in result else {}
    )


def _upload_archive(auftrag_url: str, archive: Path) -> dict[str, object]:
    """Streamt ein angekündigtes Archiv mit unverändertem Inhalt zum Adapter."""

    archive_url = f"{auftrag_url}/archive/{urllib.parse.quote(archive.name, safe='')}"
    with closing(_iter_file(archive)) as data:
        return _call_adapter(
            "PUT",
            archive_url,
            data,
            {
                "Content-Type": "application/gzip",
                "Content-Length": str(archive.stat().st_size),
            },
        )


def _call_adapter(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    payload: dict[str, object] | Iterator[bytes] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Sendet JSON oder Archivdaten und prüft die HTTP- und JSON-Antwort.

    Steueraufrufe und Archivuploads verwenden dieselbe I/O-Grenze. Archive
    werden während des Sendens aus dem übergebenen Iterator gelesen.
    """

    # JSON-Anfragen serialisieren, Archivdaten unverändert durchreichen.
    data = payload
    request_headers = dict(headers or {})
    if isinstance(payload, dict):
        data = json.dumps(payload, separators=(",", ":")).encode()
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=method, data=data, headers=request_headers)

    # Antwort lesen und Netzwerkfehler als Adapterfehler melden.
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            status = response.status
            body = response.read(_RESPONSE_LIMIT).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        with exc:
            status = exc.code
            body = exc.read(_RESPONSE_LIMIT).decode(errors="replace")
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapteraufruf ist fehlgeschlagen") from exc

    if not 200 <= status < 300:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}")

    try:
        document = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter antwortet nicht mit gültigem JSON") from exc

    if not isinstance(document, dict):
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort ist ungültig")

    if method == "DELETE":
        return document

    status = document.get("status")
    if not isinstance(status, str) or not status:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter meldet keinen Auftragsstatus")

    if status not in _ACTIVE_STATUSES and status not in _TERMINAL_STATUSES:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter meldet einen unbekannten Auftragsstatus")

    auftrag_id = document.get("auftrag_id")
    if not isinstance(auftrag_id, str) or not auftrag_id:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter liefert keine gültige Auftrags-ID")

    message = document.get("meldung")
    if message is not None and not isinstance(message, str):
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort ist ungültig")

    return document


def _iter_file(path: Path) -> Iterator[bytes]:
    """Liefert eine Archivdatei blockweise für den Adapter-Upload.

    `urllib` liest den Generator beim Senden aus, damit große Archive nicht
    vollständig im Arbeitsspeicher liegen.
    """

    with path.open("rb") as stream:
        while block := stream.read(_UPLOAD_BLOCK_SIZE):
            yield block
