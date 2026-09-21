"""Holt den Commit des Branches nach M/Text und merkt sich, wie weit er gekommen ist.

Ein Feature-Push landet in der Entwicklung, ein Merge nach `main` oder
`release/nnn` im Funktionstest. Manuell darf man die Ziele wählen, dann wird
FULL gebaut. Automatisch reicht ein DELTA, wenn derselbe Branch, dieselbe
Umgebung und dieselbe Releaselinie schon einmal erfolgreich übertragen wurden.
Den Vergleichscommit liest der Lauf aus einem GitHub-Artefakt. Fehlt er, kommt
der gesamte Projektinhalt.

Jede Umgebung bekommt ihren eigenen Adapterauftrag. Scheitert die zweite,
steht in der Meldung, dass die erste schon durch ist. Nach einer echten
Übertragung bleibt `mtext-stand.json` als Lesezeichen für den nächsten Lauf.
Dry Runs packen mit, ohne etwas zu verbuchen.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from . import adapter, config, git, github
from .process import DeliveryError, Status
from .project_packages import Scope, build_project_package, delta_scope


# Feature-Branches tragen Releaselinie und Bezeichnung im Branch-Namen
_FEATURE_BRANCH_RE = re.compile(r"feature/([0-9]{3})/(.+)")

# Name des Laufartefakts mit der M/Text-Ausgabe
_RESULT_ARTIFACT = "mtext-ergebnis"


@dataclass(frozen=True)
class Synchronisierungsplan:
    """Verbindet den Paketumfang mit den Zielumgebungen eines Sync-Laufs."""

    # FULL- oder DELTA-Umfang für alle Pakete des Laufs
    scope: Scope
    # in Ausführungsreihenfolge anzusprechende M/Text-Umgebungen
    umgebungen: list[str]
    # Releaselinie des übertragenen Commits für spätere DELTA-Abgleiche
    releaselinie: str


def _resolve_sync_branch(branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ermittelt die Releaselinie und Art der M/Text-Umgebung aus dem Branch.

    `main` und `release/nnn` verwenden die Umgebungsart "Funktionstest",
    `feature/nnn/<Bezeichnung>` die Umgebungsart "Entwicklung".
    """

    match branch:
        case "main":
            return main_releaselinie, config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST
        case name if (release_match := git.RELEASE_BRANCH_RE.fullmatch(name)):
            return release_match.group(1), config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST
        case name if (feature_match := _FEATURE_BRANCH_RE.fullmatch(name)):
            return feature_match.group(1), config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG
        case _:
            raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisierungszweig")


def latest_sync_commit(branch: str, umgebung: str, releaselinie: str) -> str | None:
    """Liest den neuesten Vergleichscommit dieses Branchs für die Zielumgebung aus dem GitHub-Artefakt."""

    # URL-Kodierung erhält die Unterscheidung von Schrägstrichen und Unterstrichen
    for artifact in github.artifacts(f"mtext-stand-{urllib.parse.quote(branch, safe='')}"):
        if artifact["expired"]:
            continue

        # den ersten Nachweis dieser Umgebung auswerten, ältere Dateien werden nicht mehr gelesen
        evidence = github.artifact_document(artifact["id"], "mtext-stand.json")
        match evidence:
            case {"commit": str(commit), "releaselinie": str(current_releaselinie), "umgebungen": list(targets)}:
                if umgebung not in targets:
                    continue
                return commit if current_releaselinie == releaselinie else None
            case _:
                raise DeliveryError(Status.SOURCE_FAILED, "Synchronisierungsnachweis ist ungültig")
    return None


def resolve_plan(source: Path, configuration: config.Configuration) -> Synchronisierungsplan:
    """Bestimmt Zielumgebungen und den durch einen erfolgreichen Abgleich belegten Umfang."""

    # Branch und Commit werden vom auslösenden Push, Merge oder manuellen Start festgehalten
    branch = os.environ["GITHUB_REF_NAME"]
    commit = git.resolve(source, "HEAD")
    event = os.environ["GITHUB_EVENT_NAME"]
    releaselinie, branch_type = _resolve_sync_branch(branch, configuration.releaselinie)
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    git.require_ancestor(source, commit, f"refs/remotes/origin/{branch}")

    # automatische Läufe verwenden den Branchstandard, manuelle Läufe die ausgewählten Ziele
    zielumgebung = os.environ.get("MTEXT_ZIELUMGEBUNG", "Branchstandard")
    entwicklung = config.MTEXT_UMGEBUNG_ART_ENTWICKLUNG
    funktionstest = config.MTEXT_UMGEBUNG_ART_FUNKTIONSTEST
    if zielumgebung not in ("Branchstandard", entwicklung, funktionstest, "Beide"):
        raise DeliveryError(Status.VALIDATION_FAILED, "Zielumgebung ist ungültig")

    # automatische Läufe bleiben an die Zielumgebung ihres Branchs gebunden
    if event != "workflow_dispatch" and zielumgebung != "Branchstandard":
        raise DeliveryError(Status.VALIDATION_FAILED, "Zielauswahl erfordert einen manuellen Start")

    # bei einem Doppelabgleich Entwicklung vor Funktionstest verarbeiten
    if zielumgebung == "Beide":
        umgebung_arten = [entwicklung, funktionstest]
    elif zielumgebung == "Branchstandard":
        umgebung_arten = [branch_type]
    else:
        umgebung_arten = [zielumgebung]

    # fachliche Releaselinie in die technischen Umgebungskennungen übersetzen
    etaps_linie = configuration.releaselinien[releaselinie]["etaps_linie"]
    umgebungen = [f"{configuration.mtext_umgebung_prefixe[e]}{etaps_linie}" for e in umgebung_arten]

    # automatische Läufe haben ein Ziel, manuelle Läufe und Dry Runs bauen FULL
    baseline = None
    if event != "workflow_dispatch" and not configuration.dry_run:
        baseline = latest_sync_commit(branch, umgebungen[0], releaselinie)

    # ein DELTA benötigt einen belegten Vorgänger für dasselbe Ziel, sonst wird FULL gebaut
    if baseline is not None:
        git.require_ancestor(source, baseline, commit)
        scope = delta_scope(source, (branch, baseline), (branch, commit))
    else:
        scope = Scope(base=None, target=(branch, commit), changes=[])
    return Synchronisierungsplan(scope, umgebungen, releaselinie)


def _workflow_result(
    plan: Synchronisierungsplan, results: list[dict[str, object]], dry_run: bool, reported: set[str],
) -> dict[str, object]:
    """Verknüpft die Git-Commits und fasst die Umgebungsstatus zusammen."""

    # festgehaltene Commits bleiben auch bei späteren Branchänderungen verlinkbar
    repository_url = f"{os.environ['GITHUB_SERVER_URL'].rstrip('/')}/{os.environ['GITHUB_REPOSITORY']}"
    commit = plan.scope.target[1]
    summary = [
        "## M/Text-Synchronisierung", "",
        f"- Umfang: {'FULL' if plan.scope.base is None else 'DELTA'}",
        f"- Zielcommit: [`{commit[:12]}`]({repository_url}/tree/{commit})",
    ]
    if plan.scope.base is not None:
        base = plan.scope.base[1]
        summary.extend((
            f"- Ausgangscommit: [`{base[:12]}`]({repository_url}/tree/{base})",
            f"- Repository-Änderungen: [GitHub-Vergleich]({repository_url}/compare/{base}..{commit})",
        ))

    # Projektumfang knapp benennen, die einzelnen Dateien bleiben im GitHub-Vergleich
    if plan.scope.base is None:
        summary.append("- Berücksichtigte Projekte: Alle konfigurierten Projekte.")
    else:
        projects = results[0]["projekte"]
        names = ", ".join(f"`{e}`" for e in projects) or "Keine."
        summary.append(f"- Berücksichtigte Projekte: {names}")

    # vorhandene Ausgaben im Laufartefakt verorten
    if dry_run:
        summary.extend(("", "Dry Run: Adapteraufträge und Archivübertragung wurden übersprungen."))
    for item in results:
        umgebung = str(item["umgebung"])
        if umgebung not in reported:
            summary.append(f"- {umgebung}: Keine M/Text-Ausgabe.")
            continue
        summary.append(f"- {umgebung}: M/Text-Ausgabe im Laufartefakt `{_RESULT_ARTIFACT}`.")

    return {
        "status": Status.ADAPTER_SKIPPED if dry_run else Status.ADAPTER_COMPLETED,
        "ergebnisse": results,
        "summary": "\n".join(summary) + "\n",
    }


def _synchronisiere_umgebung(
    configuration: config.Configuration, source: Path, scope: Scope, umgebung: str,
) -> dict[str, object]:
    """Baut und überträgt den Auftrag für eine M/Text-Umgebung."""

    # FULL überträgt jedes M/Text-Projekt, DELTA nur geänderte
    if scope.base is None:
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
    with tempfile.TemporaryDirectory() as temp:
        workdir = Path(temp)
        packages = [
            build_project_package(configuration, source, e, workdir / e, scope)
            for e in projects
        ]

        # Dry Run endet nach dem Paketbau ohne Adapterauftrag und Übertragung
        if configuration.dry_run:
            return {
                "umgebung": umgebung,
                "auftrag_id": auftrag_id,
                "result": f"Dry Run: {len(packages)} Archive erfolgreich durch M/Text verarbeitet.",
                "projekte": projects,
            }

        result = adapter.upload(umgebung, packages, auftrag_id)

    return {"umgebung": umgebung, **result, "projekte": projects}


def run() -> dict[str, object]:
    """Synchronisiert den aktuellen Commit des Branches mit den zugeordneten M/Text-Umgebungen."""

    # ausgecheckten Mandantencommit und seine Konfiguration laden
    source = config.mandant_source()
    configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])

    # Vergleichsumfang und Zielumgebungen einmalig planen
    plan = resolve_plan(source, configuration)

    # alle Zieladapter prüfen, bevor Archive für die erste Umgebung entstehen
    for umgebung in plan.umgebungen:
        adapter.check_reachability(umgebung)

    # jede Umgebung erhält einen eigenständig gebauten und übertragenen Auftrag
    results: list[dict[str, object]] = []
    report: list[str] = []
    reported: set[str] = set()
    for umgebung in plan.umgebungen:
        try:
            result = _synchronisiere_umgebung(configuration, source, plan.scope, umgebung)
        except DeliveryError as exc:
            message = f"Synchronisierung mit der M/Text-Umgebung {umgebung} fehlgeschlagen. {exc.args[0]}"
            if results:
                message += f" Bereits erfolgreich: {results[0]['umgebung']}."
            raise DeliveryError(exc.status, message) from exc

        # Adapterausgabe aus dem JSON-Ergebnis nehmen und als Datei vorbereiten
        if "result" in result:
            output = result.pop("result")
            text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2)
            report.extend((f"## {umgebung}", "", text, ""))
            reported.add(umgebung)
        results.append(result)

    # vorhandene M/Text-Ausgaben für den Upload im folgenden Workflow-Schritt schreiben
    result = _workflow_result(plan, results, configuration.dry_run, reported)
    outputs: dict[str, str] = {}

    # echte Übertragungen als lesbaren Nachweis speichern, Dry Runs begründen keine DELTA-Basis
    if not configuration.dry_run:
        evidence_path = Path(os.environ["GITHUB_WORKSPACE"]) / "mtext-stand.json"
        evidence_path.write_text(json.dumps({
            "commit": plan.scope.target[1],
            "releaselinie": plan.releaselinie,
            "umgebungen": plan.umgebungen,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs["nachweis_path"] = evidence_path.as_posix()
        # Branch für Speicherung und Abfrage identisch kodieren
        outputs["nachweis_name"] = f"mtext-stand-{urllib.parse.quote(plan.scope.target[0], safe='')}"

    if report:
        path = Path(os.environ["GITHUB_WORKSPACE"]) / f"{_RESULT_ARTIFACT}.txt"
        path.write_text("\n".join(report), encoding="utf-8")
        outputs.update({"ergebnis_path": path.as_posix(), "ergebnis_name": _RESULT_ARTIFACT})
    result["outputs"] = outputs
    return result
