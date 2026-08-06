"""Kommandozeileneinstieg für die Rückmeldung im Mandanten-Repository."""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery.github_release import publish_github_release
from lbs_delivery.process import execute


def run() -> dict[str, object]:
    """Veröffentlicht Zusammenfassung und Informationsdateien als GitHub Release."""

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    return publish_github_release(
        manifest_path=workspace / "dist" / "manifest.json",
        artifact_root=workspace / "dist",
        api_url=os.environ["GITHUB_API_URL"],
        server_url=os.environ["GITHUB_SERVER_URL"],
        repository=os.environ["SOURCE_REPOSITORY"],
        release_tag=os.environ["RELEASE_TAG"],
        token=os.environ["MANDANT_REPOSITORY_TOKEN"],
    )


if __name__ == "__main__":
    raise SystemExit(execute(run))
