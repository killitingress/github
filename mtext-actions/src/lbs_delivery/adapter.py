"""Führt M/Text-Synchronisierungen über die HTTP-Schnittstelle des Adapters aus."""

from __future__ import annotations

import json
import sys
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
from .project_packages import ProjectPackage


# Adapterantworten werden erstmal auf 10 MB begrenzt
# TODO wie mit überlangen Antworten umgehen? kann bei M/Text result passieren
_RESPONSE_LIMIT = 10 * 1024 * 1024

# Blockgröße beim Streaming der Archive zum Adapter
_UPLOAD_BLOCK_SIZE = 1024 * 1024

# Polling-Interval in Sekunden
_POLL_INTERVAL_SECONDS = 5

# URL-Muster des Adapters. `{umgebung}` ist Präfix und ETAPS-Linie.
_ADAPTER_URL = "http://{umgebung}.ltoma.intern/vMtextAdapter"


def check_reachability(umgebung: str) -> None:
    """Prüft Erreichbarkeit des /version Endpunkts und protokolliert die Antwort"""

    # Versionsendpunkt abrufen, urlopen meldet HTTP- und Verbindungsfehler
    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/version"
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            if response.status != 200:
                raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter unter {url} antwortet mit HTTP {response.status}")
            # Antwortzeile nach STDERR schreiben
            print(response.read().decode().strip(), file=sys.stderr)
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Versionsabfrage unter {url} ist fehlgeschlagen: {exc}") from exc


def resume_existing(umgebung: str, auftrag_id: str) -> dict[str, object] | None:
    """Sucht Auftrag per id und schließt diesen ab, falls er noch am Leben ist,
    oder schießt ihn ab, wenn er im Wald steht. Gibt None zurück wenn es keinen
    solchen Auftrag (mehr) gibt."""

    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2"
    auftrag_url = f"{url}/{urllib.parse.quote(auftrag_id, safe='')}"

    # Das ist etwas seltsam hier: der Adapter antwortet HTTP 404, wenn es den
    # Auftrag nicht gibt - und anders als sonst ist 404 hier OK, da es sowieso
    # das erwartete Ergebnis ist (wieso sollte der Auftrag schon existieren?) -
    # daher wird mittels not_found_ok=True das 404 auf None umgesetzt...
    result = _call_adapter("GET", auftrag_url, not_found_ok=True)
    if result is None:
        return None

    # wenn es den Auftrag schon gibt, er aber in einem Status ist, in dem er
    # nicht sauber beendet werden kann, wird er hier entfernt
    if result["status"] in {"ready", "uploading", "failed"}:
        _call_adapter("DELETE", auftrag_url)
        return None

    # Auftrag regulär abschließen
    return _finish_job(umgebung, result)


def upload(umgebung: str, pakete: list[ProjectPackage], auftrag_id: str) -> dict[str, object]:
    """Legt einen Auftrag an, lädt die Pakete hoch und wartet auf das Ergebnis."""

    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2"

    # Pakete unter der Auftrags-ID beim Adapter anmelden
    archive_list = [
        {"name": paket.archive.name, "information": paket.information} for paket in pakete
    ]
    payload = {"archive": archive_list}
    auftrag_url = f"{url}/{urllib.parse.quote(auftrag_id, safe='')}"
    result = _call_adapter("POST", auftrag_url, payload)

    # noch erwartete Archive nacheinander als unveränderten Datenstrom übertragen
    if result["status"] in {"ready", "uploading"}:
        for paket in pakete:
            result = _upload_archive(auftrag_url, paket.archive)
            if result["status"] not in {"ready", "uploading"}:
                break

    return _finish_job(umgebung, result)


def _finish_job(umgebung: str, result: dict[str, object]) -> dict[str, object]:
    """Wartet auf das Auftragsergebnis und räumt nach Erfolg oder Fehler auf.

    Neubau und Wiederanlauf verwenden denselben Abschluss. Ein inzwischen
    fehlgeschlagener Auftrag beendet den Versuch ohne erneute Verarbeitung.
    """

    # übergebene Auftrags-ID für Status und Aufräumen verwenden
    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2"
    auftrag_id = result["auftrag_id"]
    auftrag_url = f"{url}/{urllib.parse.quote(auftrag_id, safe='')}"

    # Verarbeitung nach dem Upload bis zu einem Endstatus abfragen
    while result["status"] not in {"succeeded", "failed"}:
        result = _call_adapter("GET", auftrag_url)
        if result["status"] not in {"succeeded", "failed"}:
            time.sleep(_POLL_INTERVAL_SECONDS)

    # Auftrag entfernen, ohne eine M/Text-Fehlermeldung zu überschreiben
    message = result.get("message") or "M/Text-Synchronisierung ist fehlgeschlagen"
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
    *,
    not_found_ok: bool = False,
) -> dict[str, object] | None:
    """Liefert eine geprüfte Adapterantwort.

    Bei HTTP 404 gibt die Funktion mit `not_found_ok` `None` zurück. Der
    Wiederanlauf nutzt das, wenn unter der Lauf-ID noch kein Auftrag liegt.
    Andere HTTP-Fehler beenden den Schritt mit `ADAPTER_FAILED`.
    """

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
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort überschreitet 10 MiB")

    if not_found_ok and http_status == 404:
        return None

    if not 200 <= http_status < 300:
        detail = body[:1000].decode(errors="replace")
        raise DeliveryError(
            Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {http_status}: {detail}",
        )

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

    if auftrag_status not in {"ready", "uploading", "processing", "succeeded", "failed"}:
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
