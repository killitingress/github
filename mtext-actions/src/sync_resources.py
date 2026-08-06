"""Kommandozeileneinstieg für die Synchronisation eines ausgewählten Quellstands nach M/Text.

Das Skript ermittelt den ausgecheckten Mandantenstand im Arbeitsbereich von
GitHub Actions, lädt seine Konfiguration und startet die Ressourcensynchronisation
für den angegebenen Commit und den auslösenden Branch. Die Synchronisation prüft
Branch und Commit vor der Übertragung.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lbs_delivery.config import Configuration, MANDANT_CONFIG_PATH, load_configuration
from lbs_delivery.git import read_file, resolve_sync_branch
from lbs_delivery.process import DeliveryError, Status, execute
from lbs_delivery.sync import sync_resources


# GitHub kennzeichnet den ersten Push eines Branches mit dieser leeren
# Vorgänger-SHA. Ohne Vorgänger kann kein Releaselinienwechsel erkannt werden.
EMPTY_PUSH_COMMIT = "0" * 40


def build_parser() -> argparse.ArgumentParser:
    """Fordert den unveränderlichen Commit für die Synchronisation an."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    return parser


def sync_from_github_context(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    commit: str,
    source_branch: str,
    event_name: str,
    previous_commit: str,
) -> dict[str, object]:
    """Leitet die Synchronisationsziele aus dem GitHub-Ereignis ab.

    Manuelle Starts gleichen das Ziel ihres Branches vollständig ab. Bei einem
    Wechsel der führenden Releaselinie werden Entwicklung und Abnahme
    nacheinander verarbeitet.
    """

    releaselinie, zielstufe = resolve_sync_branch(source_branch, configuration.releaselinie)
    releasewechsel = False
    if (
        event_name == "push"
        and source_branch == "main"
        and previous_commit
        and previous_commit != EMPTY_PUSH_COMMIT
    ):
        try:
            document = json.loads(read_file(repository_root, previous_commit, MANDANT_CONFIG_PATH))
            bisherige_releaselinie = document["mandant"]["releaselinie"]
            if not isinstance(bisherige_releaselinie, str) or not bisherige_releaselinie:
                raise TypeError
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DeliveryError(
                Status.VALIDATION_FAILED,
                "Bisherige Mandantenkonfiguration ist ungültig",
            ) from exc
        releasewechsel = bisherige_releaselinie != configuration.releaselinie

    zielstufen = ("Entwicklung", "Abnahme") if releasewechsel else (zielstufe,)
    vollabgleich = event_name == "workflow_dispatch" or releasewechsel
    results: list[dict[str, object]] = []
    successful_stages: list[str] = []
    for zielstufe in zielstufen:
        try:
            result = sync_resources(
                configuration,
                repository_root=repository_root,
                commit=commit,
                source_branch=source_branch,
                releaselinie=releaselinie,
                zielstufe=zielstufe,
                vollabgleich=vollabgleich,
            )
        except DeliveryError as exc:
            message = f"Synchronisation nach {zielstufe} fehlgeschlagen."
            if successful_stages:
                message += f" Bereits erfolgreich: {', '.join(successful_stages)}."
            message += f" {exc.args[0]}"
            raise DeliveryError(exc.status, message) from exc
        results.append({"zielstufe": zielstufe, **result})
        successful_stages.append(zielstufe)

    response: dict[str, object] = {
        "status": Status.ADAPTER_ACCEPTED.value,
        "synchronisationen": results,
    }
    if configuration.warnungen:
        response["warnungen"] = list(configuration.warnungen)
    return response


def run() -> dict[str, object]:
    """Startet die Ressourcensynchronisation aus dem GitHub-Ereigniskontext.

    Der Ereigniskontext legt Releaselinie und Zielstufe fest. Der
    Synchronisationskern prüft den Commit und aktualisiert das Ziel direkt aus
    dem Checkout.
    """

    # Argumente und den vertrauenswürdigen Ereigniskontext auslesen.
    arguments = build_parser().parse_args()
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    repository_root = workspace / "source"
    configuration = load_configuration(repository_root, os.environ["GITHUB_REPOSITORY"])
    # Der GitHub-Kontext legt Zielstufen, Vollabgleich und Reihenfolge fest.
    return sync_from_github_context(
        configuration,
        repository_root=repository_root,
        commit=arguments.commit,
        source_branch=os.environ["GITHUB_REF_NAME"],
        event_name=os.environ["GITHUB_EVENT_NAME"],
        previous_commit=os.environ.get("MTEXT_PREVIOUS_COMMIT", ""),
    )


if __name__ == "__main__":
    raise SystemExit(execute(run))
