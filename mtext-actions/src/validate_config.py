"""Kommandozeileneinstieg für die Prüfung der Konfiguration eines Mandanten-Repositories.

Das Skript lädt die Mandantenkonfiguration aus dem ausgecheckten Repository und
gleicht sie mit den zentralen Mandanten- und Releaselinienzuordnungen ab. Das
Ergebnis enthält Mandantenkürzel, Repository, Releaselinien und Warnungen.
"""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery.config import load_configuration
from lbs_delivery.process import Status, execute


def run() -> dict[str, object]:
    """Lädt die Konfiguration des aufrufenden Repositories und gibt die Workflow-Übersicht zurück.

    `load_configuration` prüft Mandantenidentität, Hostprofile, Releaselinien
    und die lieferbaren Projektverzeichnisse. Synchronisation und Releasebau
    laden ihre Konfiguration auf dieselbe Weise.
    """

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    configuration = load_configuration(workspace / "source", os.environ["GITHUB_REPOSITORY"])
    result: dict[str, object] = {
        "status": Status.CONFIG_VALIDATED.value,
        "mandanten_kuerzel": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": configuration.releaselinie,
        "releaselinien": sorted(configuration.releaselinien),
    }
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)
    return result


if __name__ == "__main__":
    raise SystemExit(execute(run))
