"""Übersetzt Lieferergebnisse und Fehler in den Prozessvertrag der Workflows.

Die Kommandozeileneinstiege geben über dieses Modul bei Erfolg ein JSON-Ergebnis
und bei Fehlern stabile Statusmeldungen mit den dokumentierten Exitcodes aus.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from enum import Enum


class Status(str, Enum):
    # Mandanten- und Releaselinienkonfiguration sind für die folgenden Schritte verwendbar.
    CONFIG_VALIDATED = "CONFIG_VALIDATED"
    # Eingabedaten verletzen einen fachlichen oder technischen Prüfvertrag.
    VALIDATION_FAILED = "VALIDATION_FAILED"
    # Checkout, Commit, Branch oder Tag sind nicht als Quelle verwendbar.
    SOURCE_FAILED = "SOURCE_FAILED"
    # Ein Paket, Manifest oder eine lokale Lieferdatei ist nicht verwendbar.
    PACKAGE_FAILED = "PACKAGE_FAILED"
    # Die lokalen Lieferartefakte wurden erfolgreich vorbereitet.
    ARTIFACT_READY = "ARTIFACT_READY"
    # Staging oder Ersetzung der Projekte unter serverSync ist fehlgeschlagen.
    RESOURCE_TRANSFER_FAILED = "RESOURCE_TRANSFER_FAILED"
    # Der Adapter hat die Synchronisationsanfrage angenommen.
    ADAPTER_ACCEPTED = "ADAPTER_ACCEPTED"
    # Adapteraufruf oder HTTP-Antwort sind fehlgeschlagen.
    ADAPTER_FAILED = "ADAPTER_FAILED"
    # FTP und JES haben Paket und JCL angenommen.
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    # FTP-Verbindung, Paketübertragung oder JES-Übergabe sind fehlgeschlagen.
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"


# Stabile Exitcodes unterscheiden die dokumentierten Fehlerklassen, ohne dass
# der Workflow dafür die lesbaren Fehlermeldungen auswerten muss.
_EXIT_CODES = {
    Status.VALIDATION_FAILED: 2,
    Status.SOURCE_FAILED: 3,
    Status.PACKAGE_FAILED: 4,
    Status.RESOURCE_TRANSFER_FAILED: 5,
    Status.ADAPTER_FAILED: 6,
    Status.MAINFRAME_TRANSFER_FAILED: 7,
}


class DeliveryError(RuntimeError):
    """Verbindet einen stabilen Lieferstatus mit einer sicheren Meldung für den Betrieb.

    Die Einstiegspunkte leiten aus dem Status den Exitcode ab. Der Fehlertext
    bleibt zugleich für die Ausgabe im Workflow-Log geeignet.
    """

    def __init__(self, status: Status, message: str) -> None:
        """Erzeugt einen Fehler für den durch `status` bezeichneten Lieferschritt.

        Die ursprüngliche Meldung bleibt der Inhalt der Exception. Reguläres
        Exception-Verhalten und Workflow-Ausgabe verwenden damit dieselbe Quelle.
        """

        super().__init__(message)
        self.status = status

    @property
    def exit_code(self) -> int:
        """Gibt den dokumentierten Prozess-Exitcode dieser Fehlerklasse zurück.

        Statuswerte ohne eigene erwartete Fehlerklasse verwenden den allgemeinen
        von null verschiedenen Exitcode.
        """

        return _EXIT_CODES.get(self.status, 1)

    def __str__(self) -> str:
        """Formatiert ein stabiles Statuspräfix mit der Meldung für den Betrieb.

        Dadurch bleibt die Logausgabe maschinell erkennbar, ohne interne
        Exception-Details offenzulegen.
        """

        return f"{self.status.value}: {super().__str__()}"


def execute(operation: Callable[[], dict[str, object]]) -> int:
    """Führt einen Lieferablauf aus und gibt sein Prozessergebnis für GitHub Actions aus.

    Bekannte fachliche und lokale Systemfehler werden zu knappen Meldungen und
    stabilen Exitcodes. Erfolgreiche Ergebnisse erscheinen als JSON. Warnungen
    bleiben auf stderr, damit stdout maschinell verarbeitet werden kann.
    """

    try:
        result = operation()
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except KeyError as exc:
        print(f"{Status.VALIDATION_FAILED.value}: GitHub-Runnerkontext fehlt: {exc.args[0]}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"{Status.VALIDATION_FAILED.value}: lokale Dateioperation fehlgeschlagen: {exc}", file=sys.stderr)
        return 2

    for warnung in result.get("warnungen", []):
        print(f"WARNUNG: {warnung}", file=sys.stderr)
    print(json.dumps(result, sort_keys=True))
    return 0
