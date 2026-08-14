"""Kommandozeileneinstieg für die Synchronisation eines ausgewählten Quellstands nach M/Text.

Das Skript ermittelt den ausgecheckten Mandantenstand im Arbeitsbereich von
GitHub Actions, lädt seine Konfiguration und startet die Ressourcensynchronisation
für den angegebenen Commit und den auslösenden Branch.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lbs_delivery import config, git, process, sync


# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger.
EMPTY_PUSH_COMMIT = "0" * 40


def build_parser() -> argparse.ArgumentParser:
    """Fordert die Commit-SHA für die Synchronisation an."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    return parser


def sync_from_github_context(
    configuration: config.Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    source_branch: str,
    event_name: str,
    previous_commit: str,
) -> dict[str, object]:
    """Leitet Zielstufen und Umfang aus Branch und GitHub-Ereignis ab."""

    releaselinie, zielstufe = git.resolve_sync_branch(source_branch, configuration.releaselinie)

    # Push nach `main` kann die Releaselinie wechseln. Der Vorgänger-Commit liefert den bisherigen Wert.
    releasewechsel = False
    if event_name == "push" and source_branch == "main" and previous_commit and previous_commit != EMPTY_PUSH_COMMIT:
        document = json.loads(git.read_file(repository_root, previous_commit, config.MANDANT_CONFIG_PATH))
        releasewechsel = document["mandant"]["releaselinie"] != configuration.releaselinie

    # Releaselinienwechsel synchronisiert beide M/Text-Ziele vollständig.
    # Ein manueller Start gleicht das Ziel seines Branches vollständig ab.
    zielstufen = config.MTEXT_ZIEL_REIHENFOLGE if releasewechsel else (zielstufe,)
    vollabgleich = event_name == "workflow_dispatch" or releasewechsel
    results: list[dict[str, object]] = []
    successful_stages: list[str] = []

    for zielstufe in zielstufen:
        try:
            results.append({"zielstufe": zielstufe, **sync.sync_resources(
                configuration,
                repository_root=repository_root,
                commit=commit,
                source_branch=source_branch,
                releaselinie=releaselinie,
                zielstufe=zielstufe,
                vollabgleich=vollabgleich,
            )})
        except process.DeliveryError as exc:
            detail = f" Bereits erfolgreich: {', '.join(successful_stages)}." if successful_stages else ""
            raise process.DeliveryError(
                exc.status,
                f"Synchronisation mit dem M/Text-Ziel {zielstufe} fehlgeschlagen.{detail} {exc.args[0]}",
            ) from exc
        successful_stages.append(zielstufe)

    return {"status": process.Status.ADAPTER_ACCEPTED.value, "synchronisationen": results} | (
        {"warnungen": list(configuration.warnungen)} if configuration.warnungen else {}
    )


def run() -> dict[str, object]:
    """Startet die Synchronisation mit den Angaben des GitHub-Laufs."""

    arguments = build_parser().parse_args()
    repository_root = Path(os.environ["GITHUB_WORKSPACE"]) / "source"
    configuration = config.load_configuration(repository_root, os.environ["GITHUB_REPOSITORY"])

    return sync_from_github_context(
        configuration,
        repository_root=repository_root,
        commit=arguments.commit,
        source_branch=os.environ["GITHUB_REF_NAME"],
        event_name=os.environ["GITHUB_EVENT_NAME"],
        previous_commit=os.environ.get("MTEXT_PREVIOUS_COMMIT", ""),
    )


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
