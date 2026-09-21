"""Spricht den M/Text-Adapter über HTTP `/sync2` an.

Die Basis-URL ist `http://{umgebung}.ltoma.intern/vMtextAdapter`. Die
Auftrags-ID verbindet GitHub-Lauf und Mandantenkürzel. Vor dem Paketbau fragt
der Client die Ausführung ab. HTTP 404 heißt, dass noch kein Auftrag liegt.
Sonst übernimmt oder entfernt er ihn je nach Status.

Ein neuer Auftrag entsteht mit POST (HTTP 201) und den angekündigten Archiven.
PUT überträgt die `.tgz`-Bytes unverändert. GET `/execution` wird alle fünf
Sekunden wiederholt, bis `succeeded` oder `failed` vorliegt. Danach folgt
DELETE. Fachliche Fehler kommen als HTTP 200 mit `status: failed`. Netz- und
Protokollfehler beenden den Schritt mit `ADAPTER_FAILED`. Das Socket-Timeout
beträgt 30 Sekunden.
"""

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

# Statusgruppen der sync2-Ausführung
_ABBRUCH_STATUS = frozenset({"ready", "uploading", "failed"})
_UPLOAD_STATUS = frozenset({"ready", "uploading"})
_END_STATUS = frozenset({"succeeded", "failed"})


def _auftrag_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL eines konkreten Adapterauftrags zurück."""

    return f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2/{urllib.parse.quote(auftrag_id, safe='')}"


def _execution_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL der Ausführung eines Adapterauftrags zurück."""

    return f"{_auftrag_url(umgebung, auftrag_id)}/execution"


def check_reachability(umgebung: str) -> None:
    """Prüft Erreichbarkeit des /version Endpunkts und protokolliert die Antwort."""

    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/version"
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            print(response.read().decode().strip(), file=sys.stderr)
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Versionsabfrage unter {url} ist fehlgeschlagen: {exc}") from exc


def resume_existing(umgebung: str, auftrag_id: str) -> dict[str, object] | None:
    """Übernimmt einen laufenden Auftrag oder entfernt einen unvollständigen.

    Gibt `None` zurück, wenn kein Auftrag vorhanden ist oder ein neuer Auftrag
    begonnen werden muss.
    """

    auftrag_url = _auftrag_url(umgebung, auftrag_id)

    # ein fehlender Auftrag ist der erwartete Neubaufall
    result = _call_adapter("GET", _execution_url(umgebung, auftrag_id), not_found_ok=True)
    if result is None:
        return None

    # wenn es den Auftrag schon gibt, er aber in einem Status ist, in dem er
    # nicht sauber beendet werden kann, wird er hier entfernt
    if result["status"] in _ABBRUCH_STATUS:
        _call_adapter("DELETE", auftrag_url)
        return None

    # Auftrag regulär abschließen
    return _finish_job(umgebung, auftrag_id, result)


def upload(umgebung: str, pakete: list[ProjectPackage], auftrag_id: str) -> dict[str, object]:
    """Legt einen Auftrag an, lädt die Pakete hoch und wartet auf das Ergebnis."""

    # Pakete unter der Auftrags-ID beim Adapter anmelden
    archive_list = [
        {"name": e.archive.name, "information": e.information} for e in pakete
    ]
    auftrag_url = _auftrag_url(umgebung, auftrag_id)
    result = _call_adapter("POST", auftrag_url, {"archive": archive_list})

    # noch erwartete Archive nacheinander als unveränderten Datenstrom übertragen
    if result["status"] in _UPLOAD_STATUS:
        for paket in pakete:
            result = _upload_archive(auftrag_url, paket.archive)
            if result["status"] not in _UPLOAD_STATUS:
                break

    return _finish_job(umgebung, auftrag_id, result)


def _finish_job(umgebung: str, auftrag_id: str, result: dict[str, object]) -> dict[str, object]:
    """Wartet auf das Auftragsergebnis und räumt nach Erfolg oder Fehler auf.

    Neubau und Wiederanlauf verwenden denselben Abschluss. Ein inzwischen
    fehlgeschlagener Auftrag beendet den Versuch ohne erneute Verarbeitung.
    """

    auftrag_url = _auftrag_url(umgebung, auftrag_id)
    execution_url = _execution_url(umgebung, auftrag_id)

    # Verarbeitung nach dem Upload bis zu einem Endstatus abfragen
    while result["status"] not in _END_STATUS:
        result = _call_adapter("GET", execution_url)
        if result["status"] not in _END_STATUS:
            time.sleep(_POLL_INTERVAL_SECONDS)

    # Auftrag entfernen, ohne eine M/Text-Fehlermeldung zu überschreiben
    try:
        _call_adapter("DELETE", auftrag_url)
    except DeliveryError as exc:
        if result["status"] == "failed":
            detail = f"{result['message']}. Auftrag konnte nicht entfernt werden: {exc.args[0]}"
            raise DeliveryError(Status.ADAPTER_FAILED, detail) from exc
        raise

    if result["status"] == "failed":
        raise DeliveryError(Status.ADAPTER_FAILED, result["message"])

    # Auftrags-ID und optionales M/Text-Ergebnis an den Workflow zurückgeben
    ergebnis: dict[str, object] = {"auftrag_id": auftrag_id}
    if result["result"] is not None:
        ergebnis["result"] = result["result"]
    return ergebnis


def _upload_archive(auftrag_url: str, archive: Path) -> dict[str, object]:
    """Streamt ein angekündigtes Archiv mit unverändertem Inhalt zum Adapter."""

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
    """Liefert die geprüfte Ausführung oder eine Löschbestätigung.

    Bei HTTP 404 gibt die Funktion mit `not_found_ok` `None` zurück. Der
    Wiederanlauf nutzt das, wenn unter der Lauf-ID noch kein Auftrag liegt.
    POST entnimmt die Ausführung aus dem angelegten Auftrag. Andere
    HTTP-Fehler beenden den Schritt mit `ADAPTER_FAILED`.
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

    expected_status = 201 if method == "POST" else 200
    if http_status != expected_status:
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
        match document.get("status"):
            case "succeeded":
                return document
            case _:
                raise DeliveryError(Status.ADAPTER_FAILED, "Adapter bestätigt das Löschen des Auftrags nicht")

    # POST liefert den Auftrag, weitere Aufrufe direkt dessen Ausführung
    if method == "POST":
        document = document.get("execution")
        if not isinstance(document, dict):
            raise DeliveryError(Status.ADAPTER_FAILED, "Adapter liefert keine gültige Ausführung")

    # zulässige Kombinationen der festen Ausführungsfelder übernehmen
    match document:
        case {"status": "failed", "message": str(message), "result": None} if message:
            return document
        case {"status": "succeeded", "message": None, "result": str() | None}:
            return document
        case {"status": "ready" | "uploading" | "processing", "message": None, "result": None}:
            return document
        case _:
            raise DeliveryError(Status.ADAPTER_FAILED, "Adapter liefert keine gültige Ausführung")


def _iter_file(path: Path) -> Iterator[bytes]:
    """Liefert eine Archivdatei blockweise, statt sie vollständig zu laden."""

    with path.open("rb") as stream:
        while block := stream.read(_UPLOAD_BLOCK_SIZE):
            yield block
