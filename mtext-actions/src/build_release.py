"""Kommandozeileneinstieg für den Artefaktbau zu einem ausgewählten Release-Tag.

Das Skript lädt die Mandantenkonfiguration aus dem ausgecheckten Repository und
übergibt den Release-Tag sowie die optionale Auslöser-SHA an den Artefaktbau.
Den Pfad des erzeugten Manifests gibt das Skript als Prozessergebnis aus.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lbs_delivery.config import load_configuration
from lbs_delivery.process import Status, execute
from lbs_delivery.release import build_release


def build_parser() -> argparse.ArgumentParser:
    """Definiert die vom aufrufenden Workflow übergebenen Angaben zum Release.

    Mit der optionalen auslösenden SHA kann ein ereignisgesteuerter Lauf belegen,
    dass sich Ereignis-Commit und ausgewählter Tag auf denselben Quellstand beziehen.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--trigger-sha", default="")
    return parser


def run() -> dict[str, object]:
    """Erzeugt die Releaseartefakte aus dem ausgecheckten Workflow-Arbeitsbereich.

    Konfiguration und Quellstand werden geprüft, bevor Dateien entstehen. Der
    zurückgegebene Manifestpfad verbindet den Releasebau mit dem Hochladen der
    Artefakte und der späteren Mainframe-Übergabe.
    """

    arguments = build_parser().parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    repository_root = workspace / "source"
    configuration = load_configuration(repository_root, os.environ["GITHUB_REPOSITORY"])
    manifest = build_release(
        configuration,
        repository_root=repository_root,
        output_directory=workspace / "dist",
        tag=arguments.tag,
        trigger_sha=arguments.trigger_sha,
    )
    result: dict[str, object] = {
        "status": Status.ARTIFACT_READY.value,
        "manifest": str(manifest),
    }
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)
    return result


if __name__ == "__main__":
    raise SystemExit(execute(run))
