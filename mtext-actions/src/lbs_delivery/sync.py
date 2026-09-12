"""Bestimmt den Sync-Umfang und übergibt Archive an den M/Text-Adapter."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import adapter, config, git, github
from .process import DeliveryError, Status
from .project_packages import Scope, build_project_package, delta_scope


# GitHub liefert für den ersten Push eines Branches diese Null-SHA als Vorgänger
_LEERER_PUSH_COMMIT = "0" * 40

# Feature-Branches tragen Releaselinie und Bezeichnung im Branch-Namen
_FEATURE_BRANCH_RE = re.compile(r"feature/([0-9]{3})/(.+)")


@dataclass(frozen=True)
class SyncPlan:
    """Verbindet den Paketumfang mit den Zielumgebungen eines Sync-Laufs."""

    # FULL- oder DELTA-Umfang für alle Pakete des Laufs
    scope: Scope
    # in Ausführungsreihenfolge anzusprechende M/Text-Umgebungen
    umgebungen: list[str]


def _historische_mandantenkonfiguration(source: Path, reference: str) -> dict[str, object]:
    """Liest die Mandantenkonfiguration eines früheren Git-Stands."""

    # versionierte Konfiguration lesen, ohne den früheren Stand auszuchecken
    try:
        document = json.loads(git.execute(source, "show", f"{reference}:{config.MANDANT_CONFIG_PATH}"))
        mandant = document["mandant"]
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Konfiguration kann nicht gelesen werden: {exc}") from exc

    if not isinstance(mandant, dict):
        raise DeliveryError(Status.SOURCE_FAILED, "Konfiguration enthält keine Mandantenangaben")
    return mandant


def _previous_main_release_line(source: Path) -> str | None:
    """Liest die Releaselinie des letzten erfolgreichen Pushs auf `main`."""

    # letzten erfolgreichen Sync-Stand aus GitHub-Historie lesen oder aus Umgebungsvariable
    reference = github.last_sync_commit(event="push") or os.environ.get("MTEXT_PREVIOUS_COMMIT", "")
    if not reference or reference == _LEERER_PUSH_COMMIT:
        return None

    # Releaselinie aus der damaligen Mandantenkonfiguration übernehmen
    releaselinie = _historische_mandantenkonfiguration(source, reference).get("releaselinie")
    if not isinstance(releaselinie, str):
        raise DeliveryError(Status.SOURCE_FAILED, "Historische Konfiguration enthält keine Releaselinie")
    return releaselinie


def _resolve_sync_branch(source_branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ermittelt die Releaselinie und Art der M/Text-Umgebung aus dem Branch.

    `main` und `release/nnn` verwenden die Umgebungsart "Funktionstest",
    `feature/nnn/<Bezeichnung>` die Umgebungsart "Entwicklung".
    """

    if source_branch == "main":
        return main_releaselinie, config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    release_match = git.RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST

    feature_match = _FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG

    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisierungszweig")


def _resolve_comparison_commit(
    source: Path, commit: str, basis_branch: str | None, letzter_sync: str | None,
) -> str | None:
    """Ermittelt den passenden Vergleichscommit für den DELTA-Sync."""

    # letzten erfolgreichen Sync übernehmen und gegen den aktuellen Stand absichern
    if letzter_sync:
        try:
            git.require_ancestor(source, letzter_sync, commit)
        except DeliveryError as exc:
            detail = "Der letzte erfolgreiche Sync-Stand liegt nicht vor diesem Branchstand. "
            detail += f"Der Lauf ist überholt oder die Branchhistorie wurde geändert. {exc.args[0]}"
            raise DeliveryError(Status.SOURCE_FAILED, detail) from exc
        return letzter_sync

    # ohne früheren Sync beginnt das DELTA eines Feature-Branches am Basis-Branch
    if basis_branch is not None:
        return git.execute(
            source, "merge-base", commit, f"refs/remotes/origin/{basis_branch}",
        ).decode("ascii").strip()
    return None


def resolve_plan(source: Path, configuration: config.Configuration) -> SyncPlan:
    """Bestimmt Vergleichsumfang und Zielumgebungen der Synchronisierung."""

    # Branchstand der Releaselinie und der zugeordneten Umgebungsart zuordnen
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

    # nur den noch aktuellen Stand des Remote-Branches verarbeiten
    git.require_ancestor(source, commit, f"refs/remotes/origin/{branch}")

    # Linienwechsel auf main brauchen ein FULL in Entwicklung und Funktionstest
    linienwechsel = False
    if branch == "main" and event != "workflow_dispatch":
        vorherige = _previous_main_release_line(source)
        linienwechsel = bool(vorherige and vorherige != configuration.releaselinie)
    umgebungen = [entwicklungsumgebung, umgebung] if linienwechsel else [umgebung]

    # manueller Abgleich und Linienwechsel prüfen und übertragen den Vollstand
    vergleichsstand = None
    if event != "workflow_dispatch" and not linienwechsel:
        basis_branch = None
        if umgebung_art == config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG:
            basis_branch = "main" if releaselinie == configuration.releaselinie else f"release/{releaselinie}"

        letzter_sync = github.last_sync_commit()
        vergleichsstand = _resolve_comparison_commit(source, commit, basis_branch, letzter_sync)

        # nach einem erfolgreichen Dry Run den Adapter mit einem Vollstand auffüllen
        if letzter_sync and not configuration.dry_run:
            vorherige_konfiguration = _historische_mandantenkonfiguration(source, letzter_sync)
            if vorherige_konfiguration.get("dry_run") is True:
                vergleichsstand = None

    # derselbe FULL- oder DELTA-Scope steuert Ressourcenprüfung und Paketbau
    if vergleichsstand is None:
        scope = Scope(von=None, bis=(branch, commit), changes=[])
    else:
        scope = delta_scope(source, (branch, vergleichsstand), (branch, commit))
    return SyncPlan(scope, umgebungen)


def _workflow_response(ergebnisse: list[dict[str, object]], dry_run: bool) -> dict[str, object]:
    """Erzeugt Ergebnis und Zusammenfassung des Sync-Workflows."""

    # vorhandene M/Text-Ausgaben in die Workflow-Zusammenfassung übernehmen
    summary = ["## M/Text-Synchronisierung"]
    if dry_run:
        summary.extend(("", "Dry Run: Adapteraufträge und Archivübertragung wurden übersprungen."))
    for entry in ergebnisse:
        if "result" not in entry:
            continue
        output = entry["result"]
        rendered = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
        summary.extend((f"### {entry['umgebung']}", "```text", rendered, "```"))

    return {
        "status": Status.ADAPTER_SKIPPED if dry_run else Status.ADAPTER_COMPLETED,
        "ergebnisse": ergebnisse,
        "summary": "\n".join(summary) + "\n",
    }


def _synchronize_umgebung(
    configuration: config.Configuration, source: Path, scope: Scope, umgebung: str,
) -> dict[str, object]:
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

    # vorhandenen echten Auftrag abschließen, bevor erneut Archive gebaut werden
    auftrag_id = f"{os.environ['GITHUB_RUN_ID']}-{configuration.kuerzel}"
    if not configuration.dry_run:
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

        # Dry Run endet nach dem Paketbau ohne Adapterauftrag und Übertragung
        if configuration.dry_run:
            return {
                "umgebung": umgebung,
                "auftrag_id": auftrag_id,
                "result": f"Dry Run: {len(pakete)} Archive erfolgreich durch M/Text verarbeitet.",
                "projekte": projects,
            }

        result = adapter.upload(umgebung, pakete, auftrag_id)

    return {"umgebung": umgebung, **result, "projekte": projects}


def run() -> dict[str, object]:
    """Synchronisiert den aktuellen Branchstand mit den zugeordneten M/Text-Umgebungen."""

    # ausgecheckten Mandantenstand und seine Konfiguration laden
    source = config.mandant_source()
    configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])

    # Vergleichsumfang und Zielumgebungen einmalig planen
    plan = resolve_plan(source, configuration)

    # alle Zieladapter prüfen, bevor Archive für die erste Umgebung entstehen
    for ziel in plan.umgebungen:
        adapter.check_reachability(ziel)

    # jede Umgebung erhält einen eigenständig gebauten und übertragenen Auftrag
    ergebnisse: list[dict[str, object]] = []
    for ziel in plan.umgebungen:
        try:
            ergebnisse.append(_synchronize_umgebung(configuration, source, plan.scope, ziel))
        except DeliveryError as exc:
            message = f"Synchronisierung mit der M/Text-Umgebung {ziel} fehlgeschlagen. {exc.args[0]}"
            if ergebnisse:
                message += f" Bereits erfolgreich: {ergebnisse[0]['umgebung']}."
            raise DeliveryError(exc.status, message) from exc

    return _workflow_response(ergebnisse, configuration.dry_run)
