"""Bestimmt den Sync-Umfang und übergibt Archive an den M/Text-Adapter."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from . import adapter, config, git, github
from .process import DeliveryError, Status
from .project_packages import Scope, build_project_package


# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger
_LEERER_PUSH_COMMIT = "0" * 40

# Release-Branches tragen ihre Releaselinie im Branch-Namen
_RELEASE_BRANCH_RE = re.compile(r"release/([0-9]{3})")

# Feature-Branches tragen Releaselinie und Bezeichnung im Branch-Namen
_FEATURE_BRANCH_RE = re.compile(r"feature/([0-9]{3})/(.+)")


def _previous_main_release_line(source: Path) -> str | None:
    """Liest die Releaselinie des letzten erfolgreichen Pushs auf `main`."""

    # letzten erfolgreichen Sync-Stand aus GitHub-Historie lesen oder aus Umgebungsvariable
    reference = github.last_sync_commit(event="push") or os.environ.get("MTEXT_PREVIOUS_COMMIT", "")
    if not reference or reference == _LEERER_PUSH_COMMIT:
        return None

    # Releaselinie aus der Konfiguration des letzten erfolgreichen Pushs auf `main` lesen
    try:
        document = json.loads(git.execute(source, "show", f"{reference}:{config.MANDANT_CONFIG_PATH}"))
        return document["mandant"]["releaselinie"]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Konfiguration kann nicht gelesen werden: {exc}") from exc


def _resolve_sync_branch(source_branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ermittelt die Releaselinie und Art der M/Text-Umgebung aus dem Branch.

    `main` und `release/nnn` verwenden die Umgebungsart "Funktionstest",
    `feature/nnn/<Bezeichnung>` die Umgebungsart "Entwicklung".
    """

    if source_branch == "main":
        return main_releaselinie, config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    release_match = _RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    feature_match = _FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG

    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisierungszweig")


def _resolve_comparison_commit(source: Path, commit: str, basis_branch: str | None) -> str | None:
    """Ermittelt den passenden Vergleichscommit für den DELTA-Sync."""

    # letzten erfolgreichen Sync als DELTA-Vergleichsstand nehmen und
    # sicherstellen, dass der aktuelle Stand davon abstammt
    vergleichsstand = github.last_sync_commit()
    if vergleichsstand:
        try:
            git.require_ancestor(source, vergleichsstand, commit)
        except DeliveryError as exc:
            detail = "Der letzte erfolgreiche Sync-Stand liegt nicht vor diesem Branchstand. "
            detail += f"Der Lauf ist überholt oder die Branchhistorie wurde geändert. {exc.args[0]}"
            raise DeliveryError(Status.SOURCE_FAILED, detail) from exc

    # als Fallback mittels `merge-base` den letzten gemeinsamen Commit vom Feature-Branch und
    # Basis-Branch bestimmen und diesen dann für das Delta nehmen
    if vergleichsstand is None and basis_branch is not None:
        vergleichsstand = git.execute(
            source, "merge-base", commit, f"refs/remotes/origin/{basis_branch}",
        ).decode("ascii").strip()

    return vergleichsstand


def _workflow_response(ergebnisse: list[dict[str, object]]) -> dict[str, object]:
    """Erzeugt Ergebnis und Zusammenfassung des Sync-Workflows."""

    # vorhandene M/Text-Ausgaben in die Workflow-Zusammenfassung übernehmen
    summary = ["## M/Text-Synchronisierung"]
    for entry in ergebnisse:
        if "result" not in entry:
            continue
        output = entry["result"]
        rendered = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
        summary.extend((f"### {entry['umgebung']}", "```text", rendered, "```"))

    return {
        "status": Status.ADAPTER_COMPLETED,
        "ergebnisse": ergebnisse,
        "summary": "\n".join(summary) + "\n",
    }


def _synchronize_umgebung(configuration: config.Configuration, source: Path, scope: Scope, umgebung: str) -> dict[str, object]:
    """Baut und überträgt den Auftrag für eine M/Text-Umgebung."""

    # FULL überträgt jedes M/Text-Projekt, DELTA nur geänderte
    if scope.von is None:
        projects = list(configuration.projects)
    else:
        projects = [
            e
            for e in configuration.projects
            if any(git.project_changes(scope.changes, e))
        ]

    # Änderungen außerhalb der Projektverzeichnisse brauchen keinen Adapterauftrag
    if not projects:
        return {"umgebung": umgebung, "projekte": []}

    # vorhandenen Auftrag abschließen, bevor erneut Archive gebaut werden
    auftrag_id = f"{os.environ['GITHUB_RUN_ID']}-{configuration.kuerzel}"
    result = adapter.resume_existing(umgebung, auftrag_id)
    if result is not None:
        return {"umgebung": umgebung, **result, "projekte": projects}

    # Archive gehören zu dieser Umgebung und bestehen bis zum Ende der Übertragung
    with tempfile.TemporaryDirectory() as temporary:
        workdir = Path(temporary)
        pakete = [
            build_project_package(configuration, source, e, workdir / e, scope)
            for e in projects
        ]
        result = adapter.upload(umgebung, pakete, auftrag_id)

    return {"umgebung": umgebung, **result, "projekte": projects}


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
    prefixe = configuration.mtext_umgebung_prefixe
    umgebung = f"{prefixe[umgebung_art]}{etaps_linie}"
    entwicklungsumgebung = f"{prefixe[config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG]}{etaps_linie}"

    # nur den noch aktuellen Stand des Remote-Branches synchronisieren
    git.require_ancestor(source, commit, f"refs/remotes/origin/{branch}")

    # Linienwechsel auf main: FULL zuerst in Entwicklung, danach in Funktionstest
    linienwechsel = False
    if branch == "main" and event != "workflow_dispatch":
        vorherige = _previous_main_release_line(source)
        linienwechsel = bool(vorherige and vorherige != configuration.releaselinie)

    # beim Linienwechsel Entwicklung vor Funktionstest synchronisieren
    umgebungen = [entwicklungsumgebung, umgebung] if linienwechsel else [umgebung]

    # alle Zieladapter prüfen, bevor Archive für die erste Umgebung entstehen
    for ziel in umgebungen:
        adapter.check_reachability(ziel)

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

    # jede Umgebung erhält einen eigenständig gebauten und übertragenen Auftrag
    ergebnisse: list[dict[str, object]] = []
    for ziel in umgebungen:
        try:
            ergebnisse.append(_synchronize_umgebung(configuration, source, scope, ziel))
        except DeliveryError as exc:
            message = f"Synchronisierung mit der M/Text-Umgebung {ziel} fehlgeschlagen. {exc.args[0]}"
            if ergebnisse:
                message += f" Bereits erfolgreich: {ergebnisse[0]['umgebung']}."
            raise DeliveryError(exc.status, message) from exc

    return _workflow_response(ergebnisse)
