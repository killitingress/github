"""Definiert stabile Workflowstatus und bereinigte fachliche Fehler."""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    """Benennt die technisch belegbaren Ergebnisse eines Delivery-Laufs."""

    VALIDATION_FAILED = "VALIDATION_FAILED"
    SOURCE_FAILED = "SOURCE_FAILED"
    PACKAGE_FAILED = "PACKAGE_FAILED"
    ARTIFACT_READY = "ARTIFACT_READY"
    RESOURCE_TRANSFER_FAILED = "RESOURCE_TRANSFER_FAILED"
    ADAPTER_ACCEPTED = "ADAPTER_ACCEPTED"
    ADAPTER_FAILED = "ADAPTER_FAILED"
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"
    NOTIFICATION_FAILED = "NOTIFICATION_FAILED"


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
