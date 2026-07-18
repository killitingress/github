"""Ruft den M/Text-Adapter synchron und ohne nachgelagertes Status-Polling auf."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from .errors import DeliveryError, Status


@dataclass(frozen=True)
class AdapterResponse:
    """Enthält den unmittelbaren HTTP-Status und Antworttext des Adapters."""

    status: int
    body: str


def call_adapter(
    url: str,
    payload: Mapping[str, str],
    *,
    timeout: float = 60.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> AdapterResponse:
    """Sendet den konfigurierten Payload per HTTPS und akzeptiert jeden 2xx-Status."""

    # Zugangsdaten und fachlicher Payload dürfen nur verschlüsselt übertragen werden.
    if not url.startswith("https://"):
        raise DeliveryError(
            Status.VALIDATION_FAILED, "Adapter-URL muss HTTPS verwenden"
        )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # Die Grenze reicht für Diagnosen und verhindert unbeschränktes Antwortlesen.
        with opener(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(65536).decode("utf-8", errors="replace")
        raise DeliveryError(
            Status.ADAPTER_FAILED,
            f"Adapter antwortet mit HTTP {exc.code}: {body[:1000]}",
        ) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeliveryError(
            Status.ADAPTER_FAILED, "Adapter-Transport fehlgeschlagen"
        ) from exc
    if status < 200 or status >= 300:
        raise DeliveryError(
            Status.ADAPTER_FAILED, f"Adapter antwortet mit HTTP {status}: {body[:1000]}"
        )
    return AdapterResponse(status=status, body=body)
