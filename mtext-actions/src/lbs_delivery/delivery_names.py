"""Historisch festgelegte Kürzel für Lieferdateien und Mainframe-Member."""

from __future__ import annotations

import re

from .errors import DeliveryError, Status


# Reguläre Ausdrücke für fachliche Projektnamen.
# Entfernt ein optionales Mandantenkürzel wie `[FI]` vor der Codezuordnung.
_FRAGMENT_SUFFIX = re.compile(r"\[[A-Z]{2}\]$")
# Historisch festgelegter Liefercode je fachlichem Basisprojekt.
_DELIVERY_CODE_BY_PROJECT = {
    "Configuration": "CONFI",
    "Fonts": "FONTS",
    "LOMS_Framework": "FRAME",
    "LOMS_Basis": "BASIS",
    "LOMS_PKA": "PKA",
    "LOMS_Autonom": "AUTON",
}
# Erlaubte Projektcodes in einem erzeugten Manifest.
DELIVERY_CODES = set(_DELIVERY_CODE_BY_PROJECT.values())


def project_code_for_name(project_name: str) -> str:
    """Löst die unveränderliche historische Dateikennung eines Projekts auf."""

    base_name = _FRAGMENT_SUFFIX.sub("", project_name)
    try:
        return _DELIVERY_CODE_BY_PROJECT[base_name]
    except KeyError as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"Projekt besitzt keine freigegebene Liefercode-Zuordnung: {project_name}",
        ) from exc
