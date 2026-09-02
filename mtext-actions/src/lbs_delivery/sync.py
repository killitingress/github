"""Bestimmt den Sync-Umfang und übergibt Archive an den M/Text-Adapter."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from . import adapter, config, git, github
from .process import DeliveryError, Status
from .project_archives import ProjectArchives, Scope, build_project_archives


# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger
_LEERER_PUSH_COMMIT = "0" * 40

# Release-Branches tragen ihre Releaselinie im Branch-Namen
_RELEASE_BRANCH_RE = re.compile(r"release/([0-9]{3})")

# Feature-Branches tragen Releaselinie und Bezeichnung im Branch-Namen
_FEATURE_BRANCH_RE = re.compile(r"feature/([0-9]{3})/(.+)")


def _previous_main_release_line(source: Path) -> str | None:
    """Liest die Releaselinie des letzten erfolgreichen Pushs auf `main`."""

    # GitHub-Historie verwenden und beim ersten Lauf auf dessen Vorgänger zurückfallen
    reference = github.last_sync_commit(event="push") or os.environ.get("MTEXT_PREVIOUS_COMMIT", "")
    if not reference or reference == _LEERER_PUSH_COMMIT:
        return None

    # historische Mandantenkonfiguration direkt aus dem betreffenden Commit lesen
    try:
        document = json.loads(git.execute(source, "show", f"{reference}:{config.MANDANT_CONFIG_PATH}"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Konfiguration kann nicht gelesen werden: {exc}") from exc

    return document["mandant"]["releaselinie"]


def _resolve_sync_branch(source_branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ermittelt aus dem Branch die Releaselinie und Art der M/Text-Umgebung.

    `main` und `release/nnn` verwenden die Art Funktionstest,
    `feature/nnn/<Bezeichnung>` die Art Entwicklung.
    """

    # `main` führt die in der Mandantenkonfiguration hinterlegte Releaselinie
    if source_branch == "main":
        return main_releaselinie, config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    release_match = _RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    feature_match = _FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG

    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisationszweig")


def _resolve_comparison_commit(source: Path, commit: str, basis_branch: str | None) -> str | None:
    """Ermittelt den Vergleichscommit für den nächsten DELTA-Sync."""

    # erfolgreicher Vorgängerlauf bildet die DELTA-Basis, ein überholter Lauf endet hier
    vergleichsstand = github.last_sync_commit()
    if vergleichsstand:
        try:
            git.require_ancestor(source, vergleichsstand, commit)
        except DeliveryError as exc:
            detail = "Der letzte erfolgreiche Sync-Stand liegt nicht vor diesem Branchstand. "
            detail += f"Der Lauf ist überholt oder die Branchhistorie wurde geändert. {exc.args[0]}"
            raise DeliveryError(Status.SOURCE_FAILED, detail) from exc

    # mittels `merge-base` den letzten gemeinsamen Commit vom Feature-Branch und
    # Basis-Branch bestimmen und diesen dann für das Delta nehmen
    if vergleichsstand is None and basis_branch is not None:
        vergleichsstand = git.execute(
            source, "merge-base", commit, f"refs/remotes/origin/{basis_branch}",
        ).decode("ascii").strip()

    return vergleichsstand


def _synchronize_environment(umgebung: str, archives: list[ProjectArchives]) -> dict[str, object]:
    """Übergibt die vorbereiteten Archive an eine M/Text-Umgebung (z.B. en01)."""

    try:
        _key = f"github-run-{os.environ['GITHUB_RUN_ID']}-{umgebung}"
        # Adapterauftrag anlegen, Archive hochladen und bis zum Endstatus warten
        adapter_ergebnis = adapter.synchronize(umgebung, archives, _key)
    except DeliveryError as exc:
        message = f"Synchronisation mit der M/Text-Umgebung {umgebung} fehlgeschlagen. {exc.args[0]}"
        raise DeliveryError(exc.status, message) from exc

    # Projektname steht im Dateinamen `_INFO_<kuerzel>-<projekt>.json`
    projects = [e.information.stem.removeprefix("_INFO_").partition("-")[2] for e in archives]

    return {"umgebung": umgebung, **adapter_ergebnis, "projekte": projects}


def _workflow_response(ergebnisse: list[dict[str, object]], warnungen: tuple[str, ...]) -> dict[str, object]:
    """Erzeugt Ergebnis und Zusammenfassung des Sync-Workflows."""

    # vorhandene M/Text-Ausgaben in die Workflow-Zusammenfassung übernehmen
    summary = ["## M/Text-Synchronisation"]
    for entry in ergebnisse:
        if "ergebnis" not in entry:
            continue
        output = entry["ergebnis"]
        rendered = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
        summary.extend((f"### {entry['umgebung']}", "```text", rendered, "```"))

    response = {
        "status": Status.ADAPTER_COMPLETED.value,
        "ergebnisse": ergebnisse,
        "summary": "\n".join(summary) + "\n",
    }

    if warnungen:
        response["warnungen"] = list(warnungen)

    return response


def run() -> dict[str, object]:
    """Synchronisiert den aktuellen Branchstand mit den zugeordneten M/Text-Umgebungen."""

    # ausgecheckten Mandantenstand und seine Konfiguration laden
    source = config.mandant_source()
    configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])

    # Branch der Releaselinie und der zugeordneten Umgebungsart zuordnen
    branch = os.environ["GITHUB_REF_NAME"]
    commit = git.resolve(source, "HEAD")
    event = os.environ["GITHUB_EVENT_NAME"]
    releaselinie, umgebung_art = _resolve_sync_branch(branch, configuration.releaselinie)
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")

    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    umgebung = f"{configuration.mtext_umgebung_prefixe[umgebung_art]}{etaps_linie}"

    # nur den noch aktuellen Stand des Remote-Branches synchronisieren
    git.require_ancestor(source, commit, f"refs/remotes/origin/{branch}")

    # Linienwechsel auf main initialisiert beide Umgebungen mit FULL
    linienwechsel = False
    if branch == "main" and event != "workflow_dispatch":
        vorherige = _previous_main_release_line(source)
        linienwechsel = bool(vorherige and vorherige != configuration.releaselinie)

    # manueller Abgleich und Linienwechsel brauchen keinen DELTA-Vergleichsstand
    vergleichsstand = None
    if event != "workflow_dispatch" and not linienwechsel:
        basis_branch = None
        if umgebung_art == config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG:
            basis_branch = "main" if releaselinie == configuration.releaselinie else f"release/{releaselinie}"
        vergleichsstand = _resolve_comparison_commit(source, commit, basis_branch)

    # Vergleichsstand und aktueller Branchstand bilden den gemeinsamen Archiv-Scope
    scope = Scope(
        von=(branch, vergleichsstand) if vergleichsstand is not None else None,
        bis=(branch, commit),
        changes=git.changes(source, vergleichsstand, commit) if vergleichsstand is not None else [],
    )

    # FULL überträgt jedes M/Text-Projekt, DELTA nur geänderte
    if scope.von is None:
        projects = list(configuration.projects)
    else:
        projects = [
            e
            for e in configuration.projects
            if any(git.project_changes(scope.changes, e))
        ]

    # Änderungen außerhalb der Projektverzeichnisse beenden den Workflow ohne Adapterauftrag
    if not projects:
        ergebnisse = [{"umgebung": umgebung, "projekte": []}]
        return _workflow_response(ergebnisse, configuration.warnungen)

    # Archive und Information folgen demselben Umfang und bleiben bis zum Abschluss bereit
    with tempfile.TemporaryDirectory() as temporary:
        archives = [
            build_project_archives(
                configuration, source, e, Path(temporary) / e,
                paket_scope=scope, information_scope=scope,
            )
            for e in projects
        ]

        # beim Linienwechsel zuerst Entwicklung, danach Funktionstest
        if linienwechsel:
            entwicklungsumgebung = (
                f"{configuration.mtext_umgebung_prefixe[config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG]}{etaps_linie}"
            )
            funktionstestumgebung = (
                f"{configuration.mtext_umgebung_prefixe[config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST]}{etaps_linie}"
            )
            entwicklung_ergebnis = _synchronize_environment(entwicklungsumgebung, archives)
            try:
                funktionstest_ergebnis = _synchronize_environment(funktionstestumgebung, archives)
            except DeliveryError as exc:
                message = f"{exc.args[0]} Bereits erfolgreich: {entwicklungsumgebung}."
                raise DeliveryError(exc.status, message) from exc
            ergebnisse = [entwicklung_ergebnis, funktionstest_ergebnis]
        else:
            ergebnisse = [_synchronize_environment(umgebung, archives)]

    return _workflow_response(ergebnisse, configuration.warnungen)
