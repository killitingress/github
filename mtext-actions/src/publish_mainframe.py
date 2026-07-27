"""Kommandozeileneinstieg für die Übergabe eines erzeugten Releases an den Mainframe.

Das Skript findet die Artefakte im Arbeitsbereich von GitHub Actions und stellt
einen temporären Ablageort für die gerenderte JCL bereit. Anschließend übernimmt
die gemeinsame Übergabelogik Prüfung und Transfer.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from lbs_delivery.config import AUTOMATION_ROOT
from lbs_delivery.mainframe import publish_mainframe
from lbs_delivery.process import execute


def run() -> dict[str, object]:
    """Prüft die Artefakte im Arbeitsbereich und führt ihre FTP-/JES-Übergabe aus.

    Die JCL-Dateien liegen in einem temporären Runner-Verzeichnis, weil sie nur
    Zwischeneingaben für den Transfer sind und nicht in das Verzeichnis der
    Releaseartefakte gehören.
    """

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    with tempfile.TemporaryDirectory(prefix="jcl-", dir=os.environ["RUNNER_TEMP"]) as temporary:
        return publish_mainframe(
            manifest_path=workspace / "dist" / "manifest.json",
            artifact_root=workspace / "dist",
            template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
            temporary_directory=temporary,
        )


if __name__ == "__main__":
    raise SystemExit(execute(run))
