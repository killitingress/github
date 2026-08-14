"""Kommandozeileneinstieg für die Rückmeldung im Mandanten-Repository."""

from __future__ import annotations

import os
from pathlib import Path

from lbs_delivery import github_release, process


def run() -> dict[str, object]:
    """Veröffentlicht Zusammenfassung und Informationsdateien als GitHub Release."""

    return github_release.publish_github_release(
        artifact_root=Path(os.environ["RELEASE_DIRECTORY"]),
        api_url=os.environ["GITHUB_API_URL"],
        server_url=os.environ["GITHUB_SERVER_URL"],
        repository=os.environ["SOURCE_REPOSITORY"],
        release_tag=os.environ["RELEASE_TAG"],
        source_sha=os.environ["TRIGGER_SHA"],
        token=os.environ["MANDANT_REPOSITORY_TOKEN"],
    )


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
