"""Kommandozeileneinstieg für die Erstellung der Dateien eines Releases.

Das Skript lädt die Mandantenkonfiguration aus dem ausgecheckten Repository und
erstellt für den Release-Tag die Pakete, JCL-Dateien und Lieferbelege. Die
optionale Auslöser-SHA muss zum Commit des Tags passen.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lbs_delivery import config, process, release


def build_parser() -> argparse.ArgumentParser:
    """Definiert die vom aufrufenden Workflow übergebenen Angaben zum Release.

    Wenn der Workflow eine Auslöser-SHA übergibt, muss sie zum Commit des Tags
    passen.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--trigger-sha", default="")
    return parser


def run() -> dict[str, object]:
    """Erzeugt Pakete, JCL-Dateien und Lieferbelege im Workflow-Arbeitsbereich."""

    arguments = build_parser().parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    source = workspace / "source"
    configuration = config.load_configuration(source, os.environ.get("SOURCE_REPOSITORY", os.environ["GITHUB_REPOSITORY"]))

    release.build_release(
        configuration,
        repository_root=source,
        output_directory=workspace / "dist",
        jcl_template=(config.AUTOMATION_ROOT / "templates/mainframe-upload.jcl").read_text(encoding="ascii"),
        tag=arguments.tag,
        trigger_sha=arguments.trigger_sha,
    )

    return {"status": process.Status.ARTIFACT_READY.value} | (
        {"warnungen": list(configuration.warnungen)} if configuration.warnungen else {}
    )


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
