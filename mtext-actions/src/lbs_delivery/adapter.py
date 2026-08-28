"""Spricht den M/Text-Adapter per HTTPS an.

Der Sync-Workflow legt hier einen Auftrag an, lädt Projektpakete hoch,
schließt den Upload ab und fragt den Verarbeitungsstatus ab. Dieses Modul
kapselt den Adaptervertrag und die HTTP-Grenze zur LTOMA-Umgebung.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from typing import Literal

from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_package import ProjectPackage


# Begrenzt gelesene Adapterantworten, damit fehlerhafte Antworten nicht den
# Arbeitsspeicher vollständig belegen.
_RESPONSE_LIMIT = 1024 * 1024

# Blockgröße beim Streaming großer Projektarchive in den Multipart-Upload.
_UPLOAD_BLOCK_SIZE = 1024 * 1024

# Abstand zwischen Statusabfragen, solange der Adapter noch verarbeitet.
_POLL_INTERVAL_SECONDS = 5

# Auftragszustände, in denen der Adapter noch arbeitet oder Dateien erwartet.
_ACTIVE_STATUSES = frozenset({"uploading", "queued", "processing"})

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
    projekte: list[str],
    packages: Iterator[tuple[str, ProjectPackage]],
    idempotency_key: str,
) -> str:
    """Führt einen Adapterauftrag von der Anlage bis zum Endstatus und Löschen aus.

    Pakete werden erst beim Upload aus dem Iterator angefordert. Ein bereits
    abgeschlossener Upload wird über den Idempotency-Key wiederaufgenommen,
    ohne die Pakete erneut zu erzeugen oder zu übertragen.
    """

    adapter_url = _SYNC_URL.format(umgebung=f"{target_prefix}{etaps_linie}")
    created = _call_adapter(
        "POST",
        adapter_url,
        {"kuerzel": kuerzel, "projekte": projekte},
        {"Idempotency-Key": idempotency_key},
    )
    auftrag_id = created["auftrag_id"]
    auftrag_url = f"{adapter_url}/{urllib.parse.quote(auftrag_id, safe='')}"

    if created["status"] == "uploading":
        for project, package in packages:
            _upload_project(auftrag_url, project, package)
        _call_adapter("POST", f"{auftrag_url}/complete")

    # Der Workflow begrenzt Upload und Warten gemeinsam auf 30 Minuten.
    while True:
        result = _call_adapter("GET", auftrag_url)
        if result["status"] in _TERMINAL_STATUSES:
            break

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

    return auftrag_id


def _upload_project(auftrag_url: str, project: str, package: ProjectPackage) -> None:
    """Bündelt Informationsdatei und Archive an der Multipart-Upload-Grenze."""

    project_url = f"{auftrag_url}/projekte/{urllib.parse.quote(project, safe='')}"
    boundary = f"mtext-{uuid.uuid4().hex}"
    upload_parts: list[tuple[str, Path, str]] = [
        ("informationsdatei", package.information, "application/json"),
        ("d_archiv", package.d_archiv, "application/gzip"),
    ]

    if package.f_archiv is not None:
        upload_parts.append(("f_archiv", package.f_archiv, "application/gzip"))

    # `Content-Length` verlangt die Gesamtgröße vor dem Senden, obwohl Archive erst
    # beim Streaming gelesen werden.
    encoded_parts: list[tuple[bytes, Path]] = []
    body_length = 0
    for field_name, path, mime_type in upload_parts:
        part_header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        encoded_parts.append((part_header, path))
        body_length += len(part_header) + path.stat().st_size + 2
    body_footer = f"--{boundary}--\r\n".encode()
    body_length += len(body_footer)

    # Bei Upload-Abbruch kann noch eine Archivdatei geöffnet sein.
    with closing(_iter_multipart_body(encoded_parts, body_footer)) as data:
        _call_adapter(
            "PUT",
            project_url,
            data,
            {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(body_length),
            },
        )


def _call_adapter(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    payload: dict[str, object] | Iterator[bytes] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Sendet JSON oder Multipart-Daten und prüft die HTTP- und JSON-Antwort.

    Steueraufrufe und Projektuploads verwenden dieselbe I/O-Grenze. Multipart-
    Daten werden während des Sendens aus dem übergebenen Iterator gelesen.
    """

    # JSON-Anfragen serialisieren, Multipart-Daten unverändert durchreichen.
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


def _iter_multipart_body(
    encoded_parts: list[tuple[bytes, Path]],
    body_footer: bytes,
) -> Iterator[bytes]:
    """Liefert den Multipart-Request-Body blockweise für den Adapter-Upload.

    `urllib` liest den Generator beim Senden aus, damit große Archive nicht
    vollständig im Arbeitsspeicher liegen.
    """

    for header, path in encoded_parts:
        yield header
        with path.open("rb") as stream:
            while block := stream.read(_UPLOAD_BLOCK_SIZE):
                yield block
        yield b"\r\n"
    yield body_footer
