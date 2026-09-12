"""Gibt die Ergebnisse der Kommandozeilenskripte für GitHub Actions aus.

Bei Erfolg erscheint ein JSON-Ergebnis auf stdout. Bei einem Fehler erscheinen
Status und Meldung auf stderr und das Skript endet mit dem zugehörigen Exitcode.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path


class Status(StrEnum):
    """Statuswerte der Kommandozeilenskripte für JSON-Ergebnis und Fehlerausgabe."""

    RESOURCE_CHECKED = "RESOURCE_CHECKED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LIEFERSTAND_ERMITTELT = "LIEFERSTAND_ERMITTELT"
    LIEFERUNG_CHECKED = "LIEFERUNG_CHECKED"
    LIEFERUNG_BESTAETIGT = "LIEFERUNG_BESTAETIGT"
    LIEFERUNG_TAGGED = "LIEFERUNG_TAGGED"
    LIEFERUNG_ABGESCHLOSSEN = "LIEFERUNG_ABGESCHLOSSEN"
    LIEFERUNG_NICHT_ABGESCHLOSSEN = "LIEFERUNG_NICHT_ABGESCHLOSSEN"
    FREIGABE_FAILED = "FREIGABE_FAILED"
    SOURCE_FAILED = "SOURCE_FAILED"
    PACKAGE_FAILED = "PACKAGE_FAILED"
    ARTIFACT_READY = "ARTIFACT_READY"
    ADAPTER_COMPLETED = "ADAPTER_COMPLETED"
    ADAPTER_SKIPPED = "ADAPTER_SKIPPED"
    ADAPTER_FAILED = "ADAPTER_FAILED"
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    MAINFRAME_SKIPPED = "MAINFRAME_SKIPPED"
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"
    GITHUB_RELEASE_PUBLISHED = "GITHUB_RELEASE_PUBLISHED"
    GITHUB_RELEASE_FAILED = "GITHUB_RELEASE_FAILED"


# Die Workflows unterscheiden Fehler anhand dieser Exitcodes.
_EXIT_CODES = {
    Status.VALIDATION_FAILED: 2,
    Status.SOURCE_FAILED: 3,
    Status.PACKAGE_FAILED: 4,
    Status.ADAPTER_FAILED: 6,
    Status.MAINFRAME_TRANSFER_FAILED: 7,
    Status.GITHUB_RELEASE_FAILED: 8,
    Status.FREIGABE_FAILED: 9,
}

# Externe FTPS- und HTTP-Aufrufe werden nach so vielen Sekunden abgebrochen.
NETWORK_TIMEOUT = 30.0


class DeliveryError(RuntimeError):
    """Enthält Status und Meldung eines erwarteten Fehlers im Workflow."""

    def __init__(self, status: Status, message: str) -> None:
        super().__init__(message)
        self.status = status

    def __str__(self) -> str:
        return f"{self.status}: {super().__str__()}"


def execute(operation: Callable[[], dict[str, object]]) -> int:
    """Führt den Schritt aus, schreibt JSON nach stdout und gibt den Exitcode zurück."""

    try:
        result = operation()
    except DeliveryError as exc:
        print(exc, file=sys.stderr)
        return _EXIT_CODES.get(exc.status, 1)
    except KeyError as exc:
        print(f"{Status.VALIDATION_FAILED}: fehlender Eingabewert: {exc.args[0]}", file=sys.stderr)
        return _EXIT_CODES[Status.VALIDATION_FAILED]
    except (OSError, UnicodeError) as exc:
        print(f"{Status.VALIDATION_FAILED}: lokale Dateioperation fehlgeschlagen: {exc}", file=sys.stderr)
        return _EXIT_CODES[Status.VALIDATION_FAILED]

    if summary := result.pop("summary", ""):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write(f"{summary}\n")

    if outputs := result.pop("outputs", {}):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.writelines(f"{name}={value}\n" for name, value in outputs.items())

    print(json.dumps(result, sort_keys=True))
    return 0
