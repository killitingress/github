"""Gibt die Ergebnisse der Kommandozeilenskripte für GitHub Actions aus.

Bei Erfolg erscheint ein JSON-Ergebnis auf stdout. Bei einem Fehler erscheinen
Status und Meldung auf stderr und das Skript endet mit dem zugehörigen Exitcode.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    # JSON- und XML-Ressourcen wurden geprüft, Befunde stehen als Warnungen bereit.
    RESOURCE_CHECKED = "RESOURCE_CHECKED"
    # Mandanten- und Releaselinienkonfiguration sind für die folgenden Schritte verwendbar.
    CONFIG_VALIDATED = "CONFIG_VALIDATED"
    # Konfiguration oder Argumente sind ungültig.
    VALIDATION_FAILED = "VALIDATION_FAILED"
    # SHA, Liefer-Tag und Lieferumfang der Vorbereitung sind festgehalten.
    LIEFERUNG_CHECKED = "LIEFERUNG_CHECKED"
    # Die vorbereitete Lieferung wurde durch dieselbe oder eine zweite Person bestätigt.
    LIEFERUNG_BESTAETIGT = "LIEFERUNG_BESTAETIGT"
    # Der Liefer-Tag wurde auf der festgehaltenen SHA erstellt.
    LIEFERUNG_TAGGED = "LIEFERUNG_TAGGED"
    # Checkout, Commit, Branch oder Tag sind nicht als Quelle verwendbar.
    SOURCE_FAILED = "SOURCE_FAILED"
    # Ein Paket, eine JCL oder eine lokale Lieferdatei ist nicht verwendbar.
    PACKAGE_FAILED = "PACKAGE_FAILED"
    # Pakete, JCL-Dateien und Informationsdateien wurden erstellt.
    ARTIFACT_READY = "ARTIFACT_READY"
    # Projektpakete konnten nicht vollständig auf CIFS bereitgestellt werden.
    RESOURCE_TRANSFER_FAILED = "RESOURCE_TRANSFER_FAILED"
    # Der Adapter hat die Synchronisationsanfrage angenommen.
    ADAPTER_ACCEPTED = "ADAPTER_ACCEPTED"
    # Adapteraufruf oder HTTP-Antwort sind fehlgeschlagen.
    ADAPTER_FAILED = "ADAPTER_FAILED"
    # FTPS und JES haben Paket und JCL angenommen.
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    # FTPS-Verbindung, Paketübertragung oder JES-Übergabe sind fehlgeschlagen.
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"
    # Zusammenfassung und Informationsdateien stehen im Mandanten-Repository bereit.
    GITHUB_RELEASE_PUBLISHED = "GITHUB_RELEASE_PUBLISHED"
    # Das GitHub Release oder seine Informationsdateien konnten nicht veröffentlicht werden.
    GITHUB_RELEASE_FAILED = "GITHUB_RELEASE_FAILED"


# Die Workflows unterscheiden Fehler anhand dieser Exitcodes und müssen dafür
# nicht den Text der Fehlermeldung auswerten.
_EXIT_CODES = {
    Status.VALIDATION_FAILED: 2,
    Status.SOURCE_FAILED: 3,
    Status.PACKAGE_FAILED: 4,
    Status.RESOURCE_TRANSFER_FAILED: 5,
    Status.ADAPTER_FAILED: 6,
    Status.MAINFRAME_TRANSFER_FAILED: 7,
    Status.GITHUB_RELEASE_FAILED: 8,
}

# Externe FTPS- und HTTP-Aufrufe werden nach so vielen Sekunden abgebrochen.
NETWORK_TIMEOUT = 10.0


class DeliveryError(RuntimeError):
    """Enthält Status und Meldung eines erwarteten Fehlers im Workflow."""

    def __init__(self, status: Status, message: str) -> None:
        """Speichert den Status zusammen mit der auszugebenden Fehlermeldung."""

        super().__init__(message)
        self.status = status

    @property
    def exit_code(self) -> int:
        """Gibt den zum Status gehörenden Exitcode zurück.

        Statuswerte ohne eigenen Eintrag verwenden Exitcode 1.
        """

        return _EXIT_CODES.get(self.status, 1)

    def __str__(self) -> str:
        """Setzt den Statuswert vor die Fehlermeldung."""

        return f"{self.status.value}: {super().__str__()}"


def execute(operation: Callable[[], dict[str, object]]) -> int:
    """Führt einen Skriptschritt aus und schreibt sein Ergebnis nach stdout.

    Lieferfehler, ungültig aufgebaute Eingaben und fehlgeschlagene
    Dateioperationen werden auf stderr ausgegeben. Warnungen stehen ebenfalls
    auf stderr, damit stdout bei Erfolg ausschließlich das JSON-Ergebnis enthält.
    Als ``outputs`` gekennzeichnete Werte schreibt der Schritt nach
    ``GITHUB_OUTPUT`` für nachfolgende Workflow-Schritte.
    """

    try:
        result = operation()
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except KeyError as exc:
        print(f"{Status.VALIDATION_FAILED.value}: fehlender Eingabewert: {exc.args[0]}", file=sys.stderr)
        return 2
    except (TypeError, AttributeError) as exc:
        print(f"{Status.VALIDATION_FAILED.value}: ungültige Eingabestruktur: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"{Status.VALIDATION_FAILED.value}: lokale Dateioperation fehlgeschlagen: {exc}", file=sys.stderr)
        return 2

    # GitHub zeigt eine vorhandene Zusammenfassung direkt beim Workflow-Check an.
    summary = result.pop("summary", "")
    if summary and (summary_path := os.environ.get("GITHUB_STEP_SUMMARY")):
        with Path(summary_path).open("a", encoding="utf-8") as stream:
            stream.write(str(summary))
            stream.write("\n")

    # Folgeschritte lesen Workflow-Ausgaben aus der von GitHub Actions vorgegebenen Datei.
    outputs = result.pop("outputs", {})
    if outputs and (output_path := os.environ.get("GITHUB_OUTPUT")):
        with Path(output_path).open("a", encoding="utf-8") as stream:
            for name, value in outputs.items():
                stream.write(f"{name}={value}\n")

    # Warnungen dürfen den Lauf nicht blockieren und gehören deshalb nach stderr.
    for warnung in result.get("warnungen", []):
        print(f"WARNUNG: {warnung}", file=sys.stderr)
    print(json.dumps(result, sort_keys=True))
    return 0
