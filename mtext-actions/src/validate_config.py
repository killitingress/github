"""Kommandozeileneinstieg für die Prüfung der Konfiguration eines Mandanten-Repositories.

Das Skript verwendet den festen Arbeitsbereich von GitHub Actions und gibt die
kleine Konfigurationsübersicht für die nachfolgenden Workflow-Jobs aus.
"""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery.config import load_configuration
from lbs_delivery.process import Status, execute


def run() -> dict[str, object]:
    """Lädt die Konfiguration des aufrufenden Repositories und gibt die Workflow-Übersicht zurück.

    Die gemeinsame Ladelogik übernimmt die vollständige Prüfung. Dadurch gilt in
    diesem frühen Workflow-Schritt derselbe Vertrag wie bei Synchronisation und
    Releasebau.
    """

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    configuration = load_configuration(workspace / "source", os.environ["GITHUB_REPOSITORY"])
    result: dict[str, object] = {
        "status": Status.CONFIG_VALIDATED.value,
        "mandanten_kuerzel": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinien": sorted(configuration.releaselinien),
    }
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)
    return result


if __name__ == "__main__":
    raise SystemExit(execute(run))
