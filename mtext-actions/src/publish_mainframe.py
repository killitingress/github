"""Kommandozeileneinstieg für die Übergabe eines Releases an den Mainframe."""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery import mainframe_release, process


def run() -> dict[str, object]:
    """Übergibt die vorbereiteten Pakete und JCL-Dateien per FTPS und JES."""

    return mainframe_release._publish_mainframe(artifact_root=Path(os.environ["RELEASE_DIRECTORY"]))


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
