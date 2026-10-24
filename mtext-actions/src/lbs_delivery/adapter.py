"""Spricht den M/Text-Adapter über HTTP `/sync2` an."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from http.client import HTTPException
from pathlib import Path
from typing import Literal, NoReturn

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
_ADAPTER_URL = "https://{umgebung}.ltoma.intern/vMtextAdapter"

# Statusgruppen der sync2-Ausführung
_RESTART_STATUSES = frozenset({"ready", "uploading", "failed"})
_UPLOAD_STATUSES = frozenset({"ready", "uploading"})
_FINAL_STATUSES = frozenset({"succeeded", "failed"})


def _auftrag_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL eines konkreten Adapterauftrags zurück."""

    return f"{_ADAPTER_URL.format(umgebung=umgebung)}/sync2/{urllib.parse.quote(auftrag_id, safe='')}"


def _execution_url(umgebung: str, auftrag_id: str) -> str:
    """Gibt die URL der execution eines Adapterauftrags zurück."""

    return f"{_auftrag_url(umgebung, auftrag_id)}/execution"


def check_reachability(umgebung: str) -> None:
    """Prüft die Erreichbarkeit des /version-Endpunkts."""

    url = f"{_ADAPTER_URL.format(umgebung=umgebung)}/version"
    logger.debug("GET %s", url)
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            logger.debug("Response = HTTP %s auf GET %s", response.status, url)
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
    try:
        result = _call_adapter("GET", _execution_url(umgebung, auftrag_id), not_found_ok=True)
    except DeliveryError as exc:
        _reraise_after_http_500(auftrag_url, auftrag_id, exc)
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
    try:
        result = _call_adapter("POST", auftrag_url, {"archive": archive_list})

        # noch erwartete Archive nacheinander als unveränderten Datenstrom übertragen
        if result["status"] in _UPLOAD_STATUSES:
            for package in packages:
                logger.info("Paket %s wird nach %s übertragen", package.archive.name, umgebung)
                result = _upload_archive(auftrag_url, package.archive)
                if result["status"] not in _UPLOAD_STATUSES:
                    break
    except DeliveryError as exc:
        _reraise_after_http_500(auftrag_url, auftrag_id, exc)

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

        try:
            result = _call_adapter("GET", execution_url)
        except DeliveryError as exc:
            _reraise_after_http_500(auftrag_url, auftrag_id, exc)
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

    # Größe ankündigen und den Inhalt blockweise lesen, statt die Datei vollständig zu laden
    size = archive.stat().st_size
    headers = {"Content-Type": "application/gzip", "Content-Length": str(size)}
    block_count = (size + _UPLOAD_BLOCK_SIZE - 1) // _UPLOAD_BLOCK_SIZE
    logger.debug(
        "Archiv %s (%d Bytes) wird in %d Blöcken zu je %d Bytes übertragen",
        archive.name, size, block_count, _UPLOAD_BLOCK_SIZE,
    )
    with archive.open("rb") as stream:
        blocks = iter(lambda: stream.read(_UPLOAD_BLOCK_SIZE), b"")
        return _call_adapter("PUT", archive_url, blocks, headers)


def _call_adapter(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    payload: dict[str, object] | Iterator[bytes] | None = None,
    headers: dict[str, str] | None = None,
    *,
    not_found_ok: bool = False,
) -> dict[str, object] | None:
    """Ruft den Adapter mit der Methode und URL auf und gibt die Antwort zurück.

    Bei HTTP 404 und `not_found_ok` gibt die Funktion `None` zurück. Andere
    HTTP-Fehler enden mit `DeliveryError`.
    TODO: ggf. fachliche Überfrachtung des 404 entfernen
    """

    # JSON-Anfragen serialisieren, Archivdaten unverändert durchreichen
    data = payload
    request_headers = dict(headers or {})
    if isinstance(payload, dict):
        data = json.dumps(payload, separators=(",", ":")).encode()
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=method, data=data, headers=request_headers)
    logger.debug("Rufe Adapter-Endpunkt '%s' mit Methode '%s' auf", url, method)

    # 4xx/5xx wirft urlopen als HTTPError, Status und Body der Adapterantwort stecken darin
    # 500 räumt den Auftrag ab, 404 ist beim initialen GET erlaubt
    try:
        try:
            response = urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT)
        except urllib.error.HTTPError as exc: # 404 oder 500
            response = exc

        with response:
            http_status = response.status
            body = response.read(_RESPONSE_LIMIT + 1)
            logger.debug("Adapter-Antwort: HTTP %s auf %s %s: %s", http_status, method, url, body[:300].decode(errors="replace"))
    except (urllib.error.URLError, OSError, HTTPException) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapteraufruf ist fehlgeschlagen: {exc}") from exc

    # bei HTTP 500 raise, damit der Aufrufer den Auftrag per DELETE entfernen kann
    if http_status == 500:
        detail = body[:1000].decode(errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP 500: {detail}", http_status=500)

    if len(body) > _RESPONSE_LIMIT:
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort überschreitet 10 MiB")

    # bei HTTP 404 ist der Auftrag noch nicht angelegt, der Aufrufer kann ihn neu anlegen
    if not_found_ok and http_status == 404:
        return None

    # bei HTTP 201 oder 200 ist der Auftrag angelegt oder die Ausführung gestartet
    if http_status not in (200, 201):
        detail = body[:1000].decode(errors="replace")
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {http_status}: {detail}")

    # Body von relevanten Antworten als JSON-Objekt übernehmen
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortete mit ungültigem JSON: {exc.args[0]}") from exc

    if not isinstance(document, dict):
        raise DeliveryError(Status.ADAPTER_FAILED, "Adapterantwort ist ungültig")

    # Prüfung ob der Auftrag ggf. gelöscht wurde
    if method == "DELETE":
        match document.get("status"):
            case "deleted":
                return document
            case status:
                raise DeliveryError(Status.ADAPTER_FAILED, f"Adapter antwortete auf DELETE nicht mit 'deleted' sondern mit '{status}'")

    # POST kapselt die Ausführung im Auftrag, GET und PUT liefern sie direkt
    execution = document.get("execution") if method == "POST" else document
    if not isinstance(execution, dict) or execution.get("status") not in ("failed", "succeeded", "ready", "uploading", "processing"):
        raise DeliveryError(
            Status.ADAPTER_FAILED,
            f"Adapter liefert keine gültige Execution: {json.dumps(execution)[:300]}",
        )

    return execution


def _reraise_after_http_500(auftrag_url: str, auftrag_id: str, error: DeliveryError) -> NoReturn:
    """Entfernt den Auftrag nach HTTP 500 und wirft den Fehler weiter."""

    if error.http_status != 500:
        raise error

    logger.info("Der Adapter hat HTTP 500 zurückgegeben, wir sollen die Löschung des Auftrags veranlassen...")
    try:
        _call_adapter("DELETE", auftrag_url)
    except DeliveryError as exc:
        detail = f"{error.args[0]}. Der Auftrag konnte nicht entfernt werden: {exc.args[0]}"
        raise DeliveryError(Status.ADAPTER_FAILED, detail) from exc
    raise error
