"""Führt M/Text-Synchronisationen über die HTTP-Schnittstelle des Adapters aus."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from contextlib import closing
from http.client import HTTPException
from pathlib import Path
from typing import Literal

from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_archives import ProjectArchives


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

# URL-Muster des Adapters. `{umgebung}` ist Präfix und ETAPS-Linie.
_ADAPTER_URL = "http://{umgebung}.ltoma.intern/vMtextAdapter"


def check_reachability(umgebung: str) -> None:
    """Prüft den Adapter vor dem Archivbau und protokolliert seine Versionsantwort."""

    # Versionsendpunkt abrufen, urlopen meldet HTTP- und Verbindungsfehler
    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/version"
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            # der Versionsendpunkt muss die Erreichbarkeit mit HTTP 200 bestätigen
            if response.status != 200:
                raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter unter {url} antwortet mit HTTP {response.status}")

            version = response.read().decode(errors="replace").strip()
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Versionsabfrage unter {url} ist fehlgeschlagen: {exc}") from exc

    # Antwortzeile ins Workflow-Log schreiben, stdout bleibt für das JSON-Ergebnis
    print(version, file=sys.stderr)


def synchronize(umgebung: str, project_archives: Iterable[ProjectArchives], idempotency_key: str) -> dict[str, object]:
    """Legt einen Adapterauftrag an, lädt seine Archive hoch und wartet auf den Endstatus."""

    # alle Projektarchive für Auftragsanlage und Upload bereithalten
    prepared_archives = list(project_archives)

    # Lieferart aus der Information bestimmt das hochzuladende Archiv je Projekt
    archive_uploads: list[tuple[Path, dict[str, object]]] = []
    for archives in prepared_archives:
        try:
            information = json.loads(archives.information.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryError(Status.ADAPTER_FAILED, f"Informationsdatei kann nicht gelesen werden: {exc}") from exc

        archive = archives.f_archiv if information["lieferart"] == "FULL" else archives.d_archiv
        archive_uploads.append((archive, information))

    # Mandantenkürzel steht im Dateinamen `_INFO_<kuerzel>-<projekt>.json`
    kuerzel = prepared_archives[0].information.stem.removeprefix("_INFO_").partition("-")[0]

    # Auftrag mit vollständiger Archivliste idempotent beim Ziel anlegen
    adapter_url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2"
    archive_list = [
        {"name": archive.name, "information": information} for archive, information in archive_uploads
    ]
    payload = {"mandant": kuerzel, "archive": archive_list}
    created = _call_adapter("POST", adapter_url, payload, {"Idempotency-Key": idempotency_key})
    auftrag_id = created["auftrag_id"]
    auftrag_url = f"{adapter_url}/{urllib.parse.quote(auftrag_id, safe='')}"
    result = created

    # noch erwartete Archive nacheinander als unveränderten Datenstrom übertragen
    if created["status"] in {"ready", "uploading"}:
        for archive, _information in archive_uploads:
            result = _upload_archive(auftrag_url, archive)
            if result["status"] not in {"ready", "uploading"}:
                break

    # Verarbeitung nach dem Upload bis zu einem Endstatus abfragen
    while result["status"] not in _TERMINAL_STATUSES:
        result = _call_adapter("GET", auftrag_url)
        if result["status"] in _ACTIVE_STATUSES:
            time.sleep(_POLL_INTERVAL_SECONDS)

    # Auftrag entfernen, ohne eine M/Text-Fehlermeldung zu überschreiben
    message = result.get("message") or "M/Text-Synchronisation ist fehlgeschlagen"
    try:
        _call_adapter("DELETE", auftrag_url)
    except DeliveryError as exc:
        if result["status"] == "failed":
            detail = f"{message}. Auftrag konnte nicht entfernt werden: {exc.args[0]}"
            raise DeliveryError(Status.ADAPTER_FAILED, detail) from exc
        raise

    if result["status"] == "failed":
        raise DeliveryError(Status.ADAPTER_FAILED, message)

    # Auftrags-ID und optionales M/Text-Ergebnis an den Workflow zurückgeben
    return {"auftrag_id": auftrag_id} | ({"result": result["result"]} if "result" in result else {})


def _upload_archive(auftrag_url: str, archive: Path) -> dict[str, object]:
    """Streamt ein angekündigtes Archiv mit unverändertem Inhalt zum Adapter."""

    # Archivname adressiert den beim Anlegen angekündigten Upload
    archive_url = f"{auftrag_url}/archive/{urllib.parse.quote(archive.name, safe='')}"

    # Dateigröße ankündigen und Datei während des PUT blockweise lesen
    headers = {"Content-Type": "application/gzip", "Content-Length": str(archive.stat().st_size)}
    with closing(_iter_file(archive)) as data:
        return _call_adapter("PUT", archive_url, data, headers)


def _call_adapter(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    payload: dict[str, object] | Iterator[bytes] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Sendet JSON oder Archivdaten und prüft die Antwort des Adapters."""

    # JSON-Anfragen serialisieren, Archivdaten unverändert durchreichen
    data = payload
    request_headers = dict(headers or {})
    if isinstance(payload, dict):
        data = json.dumps(payload, separators=(",", ":")).encode()
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=method, data=data, headers=request_headers)

    # Erfolgs- und Fehlerantworten über denselben begrenzten Lesepfad übernehmen
    try:
        try:
            response = urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT)
        except urllib.error.HTTPError as exc:
            response = exc

        with response:
            http_status = response.code if isinstance(response, urllib.error.HTTPError) else response.status
            body = response.read(_RESPONSE_LIMIT + 1)
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapteraufruf ist fehlgeschlagen: {exc}") from exc

    if len(body) > _RESPONSE_LIMIT:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort überschreitet 1 MiB")

    # nicht erfolgreiche HTTP-Antwort vor der JSON-Verarbeitung melden
    if not 200 <= http_status < 300:
        detail = body[:1000].decode(errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {http_status}: {detail}")

    # erfolgreichen Body als JSON-Objekt übernehmen
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet nicht mit gültigem JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort ist ungültig")

    if method == "DELETE":
        if document.get("status") != "succeeded":
            raise DeliveryError(Status.ADAPTER_FAILED, "Adapter bestätigt das Löschen des Auftrags nicht")
        return document

    # gemeinsame Auftragsfelder aller übrigen Antworten prüfen
    auftrag_status = document.get("status")
    if not isinstance(auftrag_status, str) or not auftrag_status:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter meldet keinen Auftragsstatus")

    if auftrag_status not in _ACTIVE_STATUSES and auftrag_status not in _TERMINAL_STATUSES:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter meldet einen unbekannten Auftragsstatus")

    auftrag_id = document.get("auftrag_id")
    if not isinstance(auftrag_id, str) or not auftrag_id:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapter liefert keine gültige Auftrags-ID")

    message = document.get("message")
    if message is not None and not isinstance(message, str):
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort ist ungültig")

    return document


def _iter_file(path: Path) -> Iterator[bytes]:
    """Liefert eine Archivdatei blockweise, statt sie vollständig zu laden."""

    with path.open("rb") as stream:
        while block := stream.read(_UPLOAD_BLOCK_SIZE):
            yield block
