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
import logging
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


logger = logging.getLogger(__name__)


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
_RESTART_STATUSES = frozenset({"ready", "uploading", "failed"})
_UPLOAD_STATUSES = frozenset({"ready", "uploading"})
_FINAL_STATUSES = frozenset({"succeeded", "failed"})


def _auftrag_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL eines konkreten Adapterauftrags zurück."""

    return f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2/{urllib.parse.quote(auftrag_id, safe='')}"


def _execution_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL der Ausführung eines Adapterauftrags zurück."""

    return f"{_auftrag_url(umgebung, auftrag_id)}/execution"


def check_reachability(umgebung: str) -> None:
    """Prüft die Erreichbarkeit des /version-Endpunkts."""

    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/version"
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            response.read()
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
    if result["status"] in _RESTART_STATUSES:
        logger.info("Vorhandener Auftrag %s in %s wird nach Status %s neu begonnen", auftrag_id, umgebung, result["status"])
        _call_adapter("DELETE", auftrag_url)
        return None

    # Auftrag regulär abschließen
    logger.info("Vorhandener Auftrag %s in %s wird mit Status %s fortgesetzt", auftrag_id, umgebung, result["status"])
    return _finish_auftrag(umgebung, auftrag_id, result)


def upload(umgebung: str, packages: list[ProjectPackage], auftrag_id: str) -> dict[str, object]:
    """Legt einen Auftrag an, lädt die Pakete hoch und wartet auf das Ergebnis."""

    # Pakete unter der Auftrags-ID beim Adapter anmelden
    archive_list = [
        {"name": e.archive.name, "information": e.information} for e in packages
    ]
    auftrag_url = _auftrag_url(umgebung, auftrag_id)
    logger.info("Auftrag %s wird in %s mit %d Paketen angelegt", auftrag_id, umgebung, len(packages))
    result = _call_adapter("POST", auftrag_url, {"archive": archive_list})

    # noch erwartete Archive nacheinander als unveränderten Datenstrom übertragen
    if result["status"] in _UPLOAD_STATUSES:
        for package in packages:
            logger.info("Paket %s wird nach %s übertragen", package.archive.name, umgebung)
            result = _upload_archive(auftrag_url, package.archive)
            if result["status"] not in _UPLOAD_STATUSES:
                break

    return _finish_auftrag(umgebung, auftrag_id, result)


def _finish_auftrag(umgebung: str, auftrag_id: str, result: dict[str, object]) -> dict[str, object]:
    """Wartet auf das Auftragsergebnis und räumt nach Erfolg oder Fehler auf.

    Neubau und Wiederanlauf verwenden denselben Abschluss. Ein inzwischen
    fehlgeschlagener Auftrag beendet den Versuch ohne erneute Verarbeitung.
    """

    auftrag_url = _auftrag_url(umgebung, auftrag_id)
    execution_url = _execution_url(umgebung, auftrag_id)

    # Status bei Wechsel melden, denselben Stand zwischen den Abfragen nicht wiederholen
    logged_status = None
    while True:
        if result["status"] != logged_status:
            logger.info("Auftrag %s in %s hat Status %s", auftrag_id, umgebung, result["status"])
            logged_status = result["status"]

        if result["status"] in _FINAL_STATUSES:
            break

        result = _call_adapter("GET", execution_url)
        if result["status"] not in _FINAL_STATUSES:
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
    output: dict[str, object] = {"auftrag_id": auftrag_id}
    if result["result"] is not None:
        output["result"] = result["result"]
    return output


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

    # Löschbestätigung getrennt vom Ergebnis der Ausführung prüfen
    if method == "DELETE":
        match document.get("status"):
            case "deleted":
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
