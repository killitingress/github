"""Bestimmt den Sync-Umfang und übergibt Archive an den M/Text-Adapter."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from . import adapter, config, git, github
from .process import DeliveryError, Status
from .project_artifacts import ChangeStand, build_project_artifacts


# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger.
EMPTY_PUSH_COMMIT = "0" * 40


def _sync_zielstufe(
    configuration: config.Configuration,
    *,
    repository_root: Path,
    stand: ChangeStand,
    releaselinie: str,
    zielstufe: str,
) -> dict[str, object]:
    """Stellt Archive und Informationen bis zum Adapterabschluss bereit.

    Das temporäre Verzeichnis hält Archive und Informationen während ihrer
    Übertragung. Der Adapter liest sie beim Anlegen des Auftrags aus dem Iterator.
    """

    projects = [
        project
        for project in configuration.projects
        if stand.von is None or any(git.project_changes(stand.changes, project))
    ]

    # Änderungen außerhalb der Projektverzeichnisse erfordern keinen Adapterlauf.
    if not projects:
        return {"status": Status.ADAPTER_COMPLETED.value, "projekte": []}

    with tempfile.TemporaryDirectory() as temporary:
        artifacts = (
            (
                project,
                build_project_artifacts(
                    configuration,
                    repository_root=repository_root,
                    output_directory=Path(temporary) / project,
                    project=project,
                    stand=stand,
                    include_empty_delta=False,
                ),
            )
            for project in projects
        )
        adapter_result = adapter.synchronize(
            configuration.mtext_ziel_prefixe[zielstufe],
            configuration.releaselinien[releaselinie]["etaps_linie"],
            kuerzel=configuration.kuerzel,
            artifacts=artifacts,
            idempotency_key=f"github-run-{os.environ['GITHUB_RUN_ID']}-{zielstufe}",
        )

    return {
        "status": Status.ADAPTER_COMPLETED.value,
        **adapter_result,
        "projekte": projects,
    }


def run(_arguments: argparse.Namespace) -> dict[str, object]:
    """Synchronisiert die Änderungen seit dem letzten erfolgreichen Branchstand.

    Der Workflow führt Läufe desselben Branches nacheinander aus. So wird der
    Vergleichsstand nach dem Abschluss des vorherigen Laufs gelesen. Ein API-
    oder Übertragungsfehler beendet den Lauf, ohne einen Erfolg zu bestätigen.
    """

    source = config.mandant_source()
    commit = git.resolve(source, "HEAD")
    source_branch = os.environ["GITHUB_REF_NAME"]
    configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])
    releaselinie, zielstufe = git.resolve_sync_branch(source_branch, configuration.releaselinie)
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")

    zielstufen = (zielstufe,)
    previous_commit = None

    # Ein manueller Start überträgt FULL an die zum Branch gehörende Zielstufe.
    if os.environ["GITHUB_EVENT_NAME"] != "workflow_dispatch":
        previous_commit = github.last_sync_commit()
        if previous_commit:
            # Ein älterer wartender Lauf oder Wiederanlauf darf den inzwischen
            # erfolgreich synchronisierten Branchstand nicht zurücksetzen.
            try:
                git.require_ancestor(source, previous_commit, commit)
            except DeliveryError as exc:
                raise DeliveryError(
                    Status.SOURCE_FAILED,
                    "Der letzte erfolgreiche Sync-Stand liegt nicht vor diesem Branchstand. "
                    "Der Lauf ist überholt oder die Branchhistorie wurde geändert.",
                ) from exc

        if source_branch == "main":
            # Ein manueller Abgleich bestätigt Funktionstest. Der erfolgreiche
            # Push zeigt, ob der Linienwechsel für beide Ziele erledigt ist.
            # Ohne erfolgreichen Push dient der Stand vor dem Push als Vergleich.
            reference = github.last_sync_commit(event="push") or os.environ.get("MTEXT_PREVIOUS_COMMIT", "")
            if reference and reference != EMPTY_PUSH_COMMIT:
                document = json.loads(git.execute(source, "show", f"{reference}:{config.MANDANT_CONFIG_PATH}"))
                if document["mandant"]["releaselinie"] != configuration.releaselinie:
                    # Der Linienwechsel initialisiert beide M/Text-Ziele mit FULL.
                    previous_commit = None
                    zielstufen = config.MTEXT_ZIEL_REIHENFOLGE
        elif previous_commit is None and zielstufe == config.MTEXT_ZIEL_ENTWICKLUNG:
            # Erstes Feature-DELTA ab dem gemeinsamen Commit mit seinem Zielbranch.
            base_branch = "main" if releaselinie == configuration.releaselinie else f"release/{releaselinie}"
            previous_commit = git.execute(
                source, "merge-base", commit, f"refs/remotes/origin/{base_branch}",
            ).decode("ascii").strip()

    git.require_ancestor(source, commit, f"refs/remotes/origin/{source_branch}")
    stand = ChangeStand(
        von=None if previous_commit is None else (source_branch, previous_commit),
        bis=(source_branch, commit),
        changes=[] if previous_commit is None else git.changes(source, previous_commit, commit),
    )

    # Ein Abbruch nennt bereits erfolgreiche Zielstufen, damit der Betrieb
    # den Stand nachvollziehen kann.
    results: list[dict[str, object]] = []
    for zielstufe in zielstufen:
        try:
            results.append(
                {
                    "zielstufe": zielstufe,
                    **_sync_zielstufe(
                        configuration,
                        repository_root=source,
                        stand=stand,
                        releaselinie=releaselinie,
                        zielstufe=zielstufe,
                    ),
                }
            )
        except DeliveryError as exc:
            done = [entry["zielstufe"] for entry in results]
            detail = f" Bereits erfolgreich: {', '.join(done)}." if done else ""
            raise DeliveryError(
                exc.status,
                f"Synchronisation mit dem M/Text-Ziel {zielstufe} fehlgeschlagen.{detail} {exc.args[0]}",
            ) from exc

    # Den unveränderten M/Text-Output der Zielstufen im Workflow anzeigen.
    summary = ["## M/Text-Synchronisation"]
    for result in results:
        if "ergebnis" not in result:
            continue
        output = result["ergebnis"]
        rendered = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
        summary.extend((f"### {result['zielstufe']}", "```text", rendered, "```"))

    return {
        "status": Status.ADAPTER_COMPLETED.value,
        "synchronisationen": results,
        "summary": "\n".join(summary) + "\n",
    } | ({"warnungen": list(configuration.warnungen)} if configuration.warnungen else {})
