"""Kommandozeileneinstieg für die Prüfung der Konfiguration eines Mandanten-Repositories.

Das Skript lädt die Mandantenkonfiguration aus dem ausgecheckten Repository und
gleicht sie mit den zentralen Mandanten-, M/Text-Ziel- und
Releaselinienzuordnungen ab. Das Ergebnis enthält Mandantenkürzel, Repository,
Releaselinien, den geltenden Freigabeweg und Warnungen.
"""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery import config, process


def run() -> dict[str, object]:
    """Prüft die Mandantenkonfiguration und gibt ihre wichtigsten Angaben zurück.

    `load_configuration` prüft Mandantenidentität, M/Text-Ziele, Hostprofile,
    Releaselinien und die lieferbaren Projektverzeichnisse. Synchronisation und
    Releasebau laden ihre Konfiguration auf dieselbe Weise.
    """

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    configuration = config.load_configuration(workspace / "source", os.environ["GITHUB_REPOSITORY"])
    result: dict[str, object] = {
        "status": process.Status.CONFIG_VALIDATED.value,
        "mandanten_kuerzel": configuration.kuerzel,
        "repository": configuration.repository,
        "releaselinie": configuration.releaselinie,
        "releaselinien": sorted(configuration.releaselinien),
        # Der Freigabeweg gehört ins Prüfergebnis, weil `direkter_tag` die
        # sicherheitsrelevante Ausnahme vom Freigabe-Pull-Request ist.
        "releasefreigabe": configuration.releasefreigabe,
    }
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)
    return result


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
