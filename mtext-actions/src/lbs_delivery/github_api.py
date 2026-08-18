"""Sendet die Anfragen an die GitHub-REST-API.

Freigabeprüfung und Release-Veröffentlichung sprechen dieselbe API. Header,
API-Version, Zeitüberschreitung und Fehlerauswertung liegen deshalb an einer
Stelle. Der aufrufende Schritt gibt den Status an, mit dem ein Fehler den
Workflow beendet.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .process import DeliveryError, NETWORK_TIMEOUT, Status


# Von GitHub für die REST-API vorgegebene Version des Anfrageformats.
API_VERSION = "2022-11-28"

# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
JSON_MEDIA_TYPE = "application/vnd.github+json"


def request(
    *,
    method: str,
    url: str,
    token: str,
    failure: Status,
    payload: dict[str, object] | None = None,
    content: bytes | None = None,
    content_type: str | None = None,
    missing_ok: bool = False,
) -> Any:
    """Sendet eine Anfrage an die GitHub-API und liest ihre JSON-Antwort.

    Die Funktion versendet JSON-Daten und Dateien. Wenn `missing_ok` gesetzt ist,
    gibt sie bei HTTP 404 `None` zurück. Andere HTTP- und Verbindungsfehler
    beenden den Schritt mit `failure`. Das Token wird im Authorization-Header
    übertragen.
    """

    body = json.dumps(payload).encode() if payload is not None else content
    headers = {
        "Accept": JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    elif content_type is not None:
        headers["Content-Type"] = content_type

    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(http_request, timeout=NETWORK_TIMEOUT) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        # Fehlende Releases dürfen bei der ersten Anlage ohne Fehler fehlen.
        if missing_ok and exc.code == 404:
            return None
        # GitHub liefert Fehlerdetails als JSON mit einem `message`-Feld.
        detail = ""
        try:
            error_body = json.loads(exc.read())
        except (UnicodeError, json.JSONDecodeError):
            pass
        else:
            match error_body:
                case {"message": str(message)}:
                    detail = message
                case _:
                    pass
        suffix = f": {detail}" if detail else ""
        raise DeliveryError(failure, f"GitHub antwortet mit HTTP {exc.code}{suffix}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeliveryError(failure, "GitHub ist nicht erreichbar") from exc

    # DELETE und manche erfolgreiche Uploads antworten ohne JSON-Körper.
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(failure, "GitHub-Antwort ist ungültig") from exc
