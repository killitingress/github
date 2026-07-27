"""Kommandozeileneinstieg für die Synchronisation eines ausgewählten Quellstands nach M/Text.

Das Skript überträgt Arbeitsbereich und Branch-Kontext von GitHub Actions in die
geprüften Eingaben der gemeinsamen Ressourcensynchronisation.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from lbs_delivery.config import load_configuration
from lbs_delivery.process import execute
from lbs_delivery.sync import sync_resources


def build_parser() -> argparse.ArgumentParser:
    """Fordert die vom Synchronisationsworkflow übergebene Commit-SHA an."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    return parser


def run() -> dict[str, object]:
    """Prüft und synchronisiert den vollständigen Projektstand aus dem Arbeitsbereich.

    Ein temporäres Runner-Verzeichnis trennt das Staging vom Checkout. Die
    eigentliche Prüfung, ob der Commit zum Remote-Branch gehört, erfolgt in
    `sync_resources`. Hinweise zum unverbindlichen Projektbestand werden
    zusammen mit dem Adapterergebnis an die gemeinsame Prozessausgabe übergeben.
    """

    # Argumente auslesen und Konfiguration laden.
    arguments = build_parser().parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    repository_root = workspace / "source"
    configuration = load_configuration(repository_root, os.environ["GITHUB_REPOSITORY"])

    # Temporäres Verzeichnis für das Staging erstellen.
    with tempfile.TemporaryDirectory(prefix="resources-", dir=os.environ["RUNNER_TEMP"]) as staging:
        result = sync_resources(
            configuration,
            repository_root=repository_root,
            commit=arguments.commit,
            source_branch=os.environ["GITHUB_REF_NAME"],
            staging_root=staging,
        )

    # Hinweise zum unverbindlichen Projektbestand anhängen.
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)

    return result


if __name__ == "__main__":
    raise SystemExit(execute(run))
