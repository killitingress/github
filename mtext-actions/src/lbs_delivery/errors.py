"""Definiert stabile Workflowstatus und bereinigte fachliche Fehler."""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    """Benennt die technisch belegbaren Ergebnisse eines Lieferlaufs."""

    # Die Konfigurationsdateien sind strukturell und fachlich konsistent.
    CONFIG_VALIDATED = "CONFIG_VALIDATED"
    # Eingaben oder Konfigurationswerte verletzen den erwarteten Vertrag.
    VALIDATION_FAILED = "VALIDATION_FAILED"
    # Git-Referenzen oder der ausgecheckte Quellstand sind nicht verwendbar.
    SOURCE_FAILED = "SOURCE_FAILED"
    # Ein Releasepaket oder Manifest konnte nicht korrekt erzeugt oder geprüft werden.
    PACKAGE_FAILED = "PACKAGE_FAILED"
    # Die lokalen Releaseartefakte sind vollständig erzeugt und geprüft.
    ARTIFACT_READY = "ARTIFACT_READY"
    # Staging oder Veröffentlichung nach serverSync ist fehlgeschlagen.
    RESOURCE_TRANSFER_FAILED = "RESOURCE_TRANSFER_FAILED"
    # Der M/Text-Adapter hat den synchronen Aufruf unmittelbar angenommen.
    ADAPTER_ACCEPTED = "ADAPTER_ACCEPTED"
    # Der M/Text-Adapter war nicht erreichbar oder hat den Aufruf abgelehnt.
    ADAPTER_FAILED = "ADAPTER_FAILED"
    # JES hat das übertragene JCL unmittelbar angenommen.
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    # Paketupload oder JES-Übergabe ist fehlgeschlagen.
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"


# Prozess-Exitcodes für die sechs Fehlerklassen der CLI.
_EXIT_CODES = {
    Status.VALIDATION_FAILED: 2,
    Status.SOURCE_FAILED: 3,
    Status.PACKAGE_FAILED: 4,
    Status.RESOURCE_TRANSFER_FAILED: 5,
    Status.ADAPTER_FAILED: 6,
    Status.MAINFRAME_TRANSFER_FAILED: 7,
}


class DeliveryError(RuntimeError):
    """Verknüpft eine nutzbare Fehlermeldung mit einem stabilen Workflowstatus."""

    def __init__(self, status: Status, message: str) -> None:
        """Speichert Status und bereinigte Meldung für CLI und Workflow."""

        super().__init__(message)
        self.status = status
        self.message = message

    @property
    def exit_code(self) -> int:
        """Liefert den zum fachlichen Status gehörenden Prozess-Exitcode."""

        return _EXIT_CODES.get(self.status, 1)

    def __str__(self) -> str:
        """Formatiert Status und Meldung für die Konsolenausgabe."""

        return f"{self.status.value}: {self.message}"
