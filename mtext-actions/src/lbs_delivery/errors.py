"""Definiert den kleinen Fehlervertrag der Kommandozeile."""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    # Mandanten- und Releaselinienkonfiguration sind gemeinsam verwendbar.
    CONFIG_VALIDATED = "CONFIG_VALIDATED"
    # Eine Eingabe verletzt einen fachlichen oder technischen Vertrag.
    VALIDATION_FAILED = "VALIDATION_FAILED"
    # Checkout, Commit, Branch oder Tag sind nicht als Quelle verwendbar.
    SOURCE_FAILED = "SOURCE_FAILED"
    # Releasepaket, Manifest oder lokale Lieferdatei ist nicht verwendbar.
    PACKAGE_FAILED = "PACKAGE_FAILED"
    # Lokale Lieferartefakte sind vollständig vorbereitet.
    ARTIFACT_READY = "ARTIFACT_READY"
    # Staging oder Ersetzung unter serverSync ist fehlgeschlagen.
    RESOURCE_TRANSFER_FAILED = "RESOURCE_TRANSFER_FAILED"
    # Der Adapter hat die Synchronisation unmittelbar angenommen.
    ADAPTER_ACCEPTED = "ADAPTER_ACCEPTED"
    # HTTP-Aufruf oder Antwort des Adapters ist fehlgeschlagen.
    ADAPTER_FAILED = "ADAPTER_FAILED"
    # FTP und JES haben Paket und JCL unmittelbar angenommen.
    MAINFRAME_SUBMITTED = "MAINFRAME_SUBMITTED"
    # FTP-Verbindung, Paketupload oder JES-Übergabe ist fehlgeschlagen.
    MAINFRAME_TRANSFER_FAILED = "MAINFRAME_TRANSFER_FAILED"


# Die Exitcodes unterscheiden die betrieblich dokumentierten Fehlerklassen.
_EXIT_CODES = {
    Status.VALIDATION_FAILED: 2,
    Status.SOURCE_FAILED: 3,
    Status.PACKAGE_FAILED: 4,
    Status.RESOURCE_TRANSFER_FAILED: 5,
    Status.ADAPTER_FAILED: 6,
    Status.MAINFRAME_TRANSFER_FAILED: 7,
}


class DeliveryError(RuntimeError):
    """Verbindet eine bereinigte Meldung mit Status und Prozess-Exitcode."""

    def __init__(self, status: Status, message: str) -> None:
        """Speichert den fehlgeschlagenen fachlichen Schritt."""
        super().__init__(message)
        self.status = status

    @property
    def exit_code(self) -> int:
        return _EXIT_CODES.get(self.status, 1)

    def __str__(self) -> str:
        return f"{self.status.value}: {super().__str__()}"
