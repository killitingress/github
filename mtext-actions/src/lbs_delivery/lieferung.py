"""Bereitet Lieferungen vor, prüft ihre Freigabe und erzeugt Liefer-Tags."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config, git, github
from .process import DeliveryError, Status
from .project_packages import delivery_report, previous_release_scope, release_scope, sha256_file


# Name des GitHub-Actions-Artefakts für das zugehörige Freigabe-Issue
_VORBEREITUNG_ARTEFAKT = "lieferung-{issue}-vorbereitungsartefakt"

# Name und Repository-Beschreibung der Freigabe-Issue-Labels
_LABEL_FREIGABE = "lieferung:freigabe"
_LABEL_GESTARTET = "lieferung:gestartet"
_LABEL_ABGESCHLOSSEN = "lieferung:abgeschlossen"
_LABEL_DRY_RUN = "dry_run"

_LIEFERUNG_LABELS: dict[str, str] = {
    _LABEL_FREIGABE: "Vorbereitete Mainframe-Lieferung wartet auf Freigabe",
    _LABEL_GESTARTET: "Freigabe angenommen, Lieferung wurde gestartet",
    _LABEL_ABGESCHLOSSEN: "Lieferlauf wurde abgeschlossen",
    _LABEL_DRY_RUN: "Externe Übergabe wird in diesem Lauf übersprungen",
}


def liefer_tag_fuer_branch(configuration: config.Configuration, branch: str) -> git.LieferTag:
    """Leitet den Liefer-Tag aus einem zulässigen Lieferzweig ab."""

    # Liefer-Tag aus dem Branch und der Releaselinie berechnen
    tag = git.LieferTag.from_lieferzweig(branch, configuration.releaselinie)
    if tag is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Branch ist kein Lieferzweig")

    # .100 bezeichnet den Vollstand und darf nicht als Teillieferung entstehen
    if tag.ist_hauptrelease and git.LieferTag.from_bereitstellung(branch) is not None:
        raise DeliveryError(Status.VALIDATION_FAILED, ".100 darf nur auf main oder release/nnn entstehen")

    # Releaselinie muss in der gemeinsamen Zielzuordnung aktiv sein
    if tag.releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, f"Releaselinie {tag.releaselinie} ist unbekannt")

    return tag


def _pruefe_lieferquelle(configuration: config.Configuration, root: Path, branch: str) -> git.LieferTag:
    """Ermittelt den Liefer-Tag und prüft, dass er noch nicht vorhanden ist."""

    # Branch und Mandantenkonfiguration legen den vorgesehenen Liefer-Tag fest
    tag = liefer_tag_fuer_branch(configuration, branch)

    # neue Vorbereitung darf keinen bereits veröffentlichten Tag überschreiben
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist bereits vorhanden")

    return tag


def _summary(configuration: config.Configuration, root: Path, tag: git.LieferTag, branch: str, sha: str) -> str:
    """Erzeugt den Lieferumfang und die Vergleichsstände als Markdown."""

    # ausgewählten Branch als Kontext der Vorbereitung nennen
    lines = [
        "## Liefer-Vorprüfung",
        "",
        "| Angabe | Wert |",
        "|---|---|",
        f"| Branch | `{branch}` |",
        "",
    ]

    # den Lieferumfang aus den beiden Vergleichsständen für das Issue erzeugen
    paket_scope = release_scope(root, tag, sha)
    vorrelease_scope = previous_release_scope(root, tag, sha)

    return "\n".join(lines) + "\n" + delivery_report(
        configuration, root, paket_scope=paket_scope, vorrelease_scope=vorrelease_scope,
    )


def _ermittle_lieferung(issue: int) -> dict[str, object]:
    """Ermittelt die Vorbereitung oder den im Freigabe-Issue genannten Liefer-Tag."""

    # jede neue Lieferung und Wiederholung erfordert Maintain oder Admin
    role = github.repository_role(os.environ["GITHUB_ACTOR"])
    if role not in ("maintain", "admin"):
        raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe erfordert Repository-Berechtigung maintain oder admin")

    # Issue als gemeinsame Grundlage für Freigabe und Wiederholung lesen
    state, labels, title = github.issue(issue)

    # offene Freigabe dem zugeordneten Vorbereitungsartefakt zuweisen
    if state == "open" and _LABEL_FREIGABE in labels:
        artifact_id = github.latest_artifact(_VORBEREITUNG_ARTEFAKT.format(issue=issue))
        if artifact_id is None:
            raise DeliveryError(Status.SOURCE_FAILED, "Für das Freigabe-Issue besteht keine Vorbereitung")

        return {
            "status": Status.LIEFERSTAND_ERMITTELT,
            "outputs": {"wiederholung": "false", "vorbereitung_artefakt_id": artifact_id},
        }

    # bereits angenommene Freigabe erneut an den Mainframe geben
    if _LABEL_GESTARTET not in labels and _LABEL_ABGESCHLOSSEN not in labels:
        raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue ist nicht zur Freigabe oder Wiederholung gekennzeichnet")

    # den beim Anlegen festgelegten Tag aus dem Titel des bekannten Issues lesen
    prefix = "Lieferung "
    suffix = " freigeben"
    if not title.startswith(prefix) or not title.endswith(suffix):
        raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue enthält keinen eindeutigen Liefer-Tag")
    try:
        tag = git.LieferTag.parse(title[len(prefix):-len(suffix)])
    except ValueError as exc:
        raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue enthält keinen gültigen Liefer-Tag") from exc

    # die gespeicherte Tag-Annotation muss auf genau dieses Issue zeigen
    record = github.tag_record(str(tag))
    if record is None or record[1] != issue:
        raise DeliveryError(Status.FREIGABE_FAILED, "Liefer-Tag fehlt oder gehört nicht zu diesem Freigabe-Issue")
    source_sha, _ = record

    return {
        "status": Status.LIEFERSTAND_ERMITTELT,
        "outputs": {
            "wiederholung": "true",
            "source_sha": source_sha,
            "liefer_tag": str(tag),
        },
    }


def _actions_lauf_url() -> str:
    """Gibt die Adresse des aktuellen GitHub-Actions-Laufs zurück."""

    return (
        f"{os.environ['GITHUB_SERVER_URL'].rstrip('/')}/{os.environ['GITHUB_REPOSITORY']}"
        f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    )


def _issue_link(issue: int) -> str:
    """Verlinkt das Freigabe-Issue aus einer Laufzusammenfassung."""

    repository = os.environ["GITHUB_REPOSITORY"]
    server = os.environ["GITHUB_SERVER_URL"].rstrip("/")
    return f"[Freigabe-Issue #{issue}]({server}/{repository}/issues/{issue})\n"


def _erstelle_freigabe_issue(tag: git.LieferTag, summary: str, dry_run: bool) -> int:
    """Erstellt das Issue mit Lieferumfang und Bedienhinweis für die Freigabe."""

    # geprüften Bericht mit Urheber und Vorbereitungslauf im Issue zeigen
    body = (
        f"{summary}\n"
        "---\n\n"
        "## Freigabe\n\n"
        f"- Vorbereitet durch: @{os.environ['GITHUB_ACTOR']} ([Actions-Lauf]({_actions_lauf_url()}))\n\n"
        "Lieferung starten durch einen Kommentar, der ausschließlich `/freigabe` enthält.\n"
    )

    # Dry Runs bereits am Freigabe-Issue sichtbar kennzeichnen
    labels = {_LABEL_FREIGABE: _LIEFERUNG_LABELS[_LABEL_FREIGABE]}
    if dry_run:
        labels[_LABEL_DRY_RUN] = _LIEFERUNG_LABELS[_LABEL_DRY_RUN]

    # Issue-Nummer bindet das spätere Laufartefakt an diese Freigabe
    return github.create_labeled_issue(
        title=f"Lieferung {tag} freigeben",
        body=body,
        labels=labels,
    )


def _pruefe_lieferung() -> dict[str, object]:
    """Hält für `check` den geprüften Branchstand und seinen Lieferumfang fest."""

    # ausgecheckten Mandantenstand einordnen und gegen Liefer-Tag und Branch prüfen
    source = config.mandant_source()
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["GITHUB_REF_NAME"]
    sha = git.resolve(source, "HEAD")
    configuration = config.Configuration.load(source, repository)
    tag = _pruefe_lieferquelle(configuration, source, branch)

    # Bericht im Freigabe-Issue veröffentlichen und den geprüften Stand daran binden
    summary = _summary(configuration, source, tag, branch, sha)
    issue = _erstelle_freigabe_issue(tag, summary, configuration.dry_run)
    vorbereitung = Path(os.environ["GITHUB_WORKSPACE"]) / config.WORKFLOW_VORBEREITUNG_DATEI
    try:
        vorbereitung.write_text(
            json.dumps({"tag": str(tag), "sha": sha, "repository": repository, "issue": issue},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Vorbereitungsartefakt kann nicht geschrieben werden: {exc}") from exc

    # Vorbereitung, Vorprüfung und Freigabeweg an den Workflow übergeben
    return {
        "status": Status.LIEFERUNG_CHECKED,
        "summary": _issue_link(issue),
        "outputs": {"vorbereitung_path": vorbereitung.as_posix(),
                    "vorbereitung_name": _VORBEREITUNG_ARTEFAKT.format(issue=issue)},
    }


def _bestaetige_lieferung(expected_issue: int) -> dict[str, object]:
    """Bestätigt die an das Freigabe-Issue gebundene Vorbereitung."""

    # Vorbereitung aus dem heruntergeladenen GitHub-Actions-Artefakt lesen
    vorbereitung = Path(os.environ["GITHUB_WORKSPACE"]) / "vorbereitung" / config.WORKFLOW_VORBEREITUNG_DATEI
    try:
        payload = json.loads(vorbereitung.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Vorbereitungsartefakt ist ungültig: {exc}") from exc

    # erwartete Angaben gemeinsam übernehmen oder das Artefakt ablehnen
    match payload:
        case {"tag": str(tag), "sha": str(sha), "repository": str(repository), "issue": int(issue)}:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt enthält nicht die erwarteten Angaben")

    # Vorbereitung dem aktuellen Repository und Freigabe-Issue zuordnen
    if repository != os.environ["GITHUB_REPOSITORY"]:
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört nicht zu diesem Repository")

    if issue != expected_issue:
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört nicht zu diesem Freigabe-Issue")

    # die erste gültige Freigabe verbrauchen, bevor Paketbau und Übergabe beginnen
    github.replace_issue_label(issue, _LABEL_FREIGABE, _LABEL_GESTARTET, _LIEFERUNG_LABELS[_LABEL_GESTARTET])

    # gestarteten Lauf im Issue verknüpfen, bevor die Verarbeitung in Folgejobs wechselt
    github.comment_issue(
        issue,
        f"Lieferung `{tag}` wurde gestartet: [Actions-Lauf]({_actions_lauf_url()})",
    )

    # bestätigten Commit und Liefer-Tag für die Folgeschritte ausgeben
    return {
        "status": Status.LIEFERUNG_BESTAETIGT,
        "summary": _issue_link(issue),
        "outputs": {"source_sha": sha, "liefer_tag": tag},
    }


def _schliesse_freigabe(issue: int, tag: git.LieferTag) -> dict[str, object]:
    """Dokumentiert die Lieferdateien und schließt ihr Freigabe-Issue."""

    # die Prüfsummen der übertragenen Archive für das Issue berechnen
    archives = sorted((Path(os.environ["RUNNER_TEMP"]) / "release").glob("*.tgz"))
    if not archives:
        raise DeliveryError(Status.PACKAGE_FAILED, "Lieferarchive fehlen")

    rows = [f"| `{e.name}` | `{sha256_file(e)}` |" for e in archives]

    # Ergebnis, Dateiliste und ausführenden Lauf im Freigabeprotokoll ergänzen
    dry_run = os.environ.get("DRY_RUN") == "true"
    result = "Dry Run ohne Mainframe-Übergabe" if dry_run else "Mainframe-Lieferung abgeschlossen"
    body = "\n".join([
        f"{result}: [Liefer-Tag `{tag}`]({os.environ['GITHUB_SERVER_URL'].rstrip('/')}/"
        f"{os.environ['GITHUB_REPOSITORY']}/tree/{tag}) ([Actions-Lauf]({_actions_lauf_url()}))",
        "",
        "| Datei | SHA-256 |",
        "|---|---|",
        *rows,
    ])
    github.complete_issue(issue, body, _LABEL_GESTARTET, _LABEL_ABGESCHLOSSEN, _LIEFERUNG_LABELS[_LABEL_ABGESCHLOSSEN])
    
    return {"status": Status.LIEFERUNG_ABGESCHLOSSEN, "summary": _issue_link(issue)}


def _erstelle_liefer_tag(tag: git.LieferTag, issue: int) -> dict[str, object]:
    """Erzeugt den Liefer-Tag mit Commit-SHA und Freigabe-Issue."""

    # identischen Tag aus einem wiederholten GitHub-Abschluss übernehmen
    source_sha = os.environ["SOURCE_SHA"]
    record = github.tag_record(str(tag))
    if record is not None and record != (source_sha, issue):
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag zeigt auf einen anderen Commit oder ein anderes Freigabe-Issue")

    # fehlenden Tag mit der bereits bekannten SHA und Issue-Nummer anlegen
    if record is None:
        github.create_tag(str(tag), source_sha, issue)

    return {"status": Status.LIEFERUNG_TAGGED}


def run(subcommand: str, tag: str | None = None, issue: int | None = None) -> dict[str, object]:
    """Führt das gewählte Lieferkommando über den einheitlichen Moduleinstieg aus."""

    # optionalen externen Text einmalig prüfen und danach als Liefer-Tag weiterreichen
    parsed_tag = None
    if tag:
        try:
            parsed_tag = git.LieferTag.parse(tag)
        except ValueError as exc:
            raise DeliveryError(Status.VALIDATION_FAILED, str(exc)) from exc

    # GitHub-Issue-Nummern sind positiv
    if issue is not None and issue <= 0:
        raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue-Nummer ist ungültig")

    # Lieferstand aus dem Freigabe-Issue ermitteln — Freigabe oder Wiederholung erkennt der Ablauf an den Labels
    if subcommand in ("resolve", "repeat"):
        if parsed_tag is not None or issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue fehlt oder Liefer-Tag wurde zusätzlich angegeben")
        return _ermittle_lieferung(issue)

    # Vorbereitung prüfen und Freigabe-Issue anlegen, der Liefer-Tag folgt aus dem Branch
    if subcommand == "check":
        if parsed_tag is not None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag wird aus dem Branch ermittelt")
        return _pruefe_lieferung()

    # Freigabe annehmen und das Issue von freigabe auf gestartet setzen
    if subcommand == "confirm":
        if issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue fehlt")
        return _bestaetige_lieferung(issue)

    # fehlgeschlagenen Lauf im Issue vermerken, ohne das Label zurückzusetzen — Wiederholung bleibt möglich
    if subcommand == "incomplete":
        if issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue fehlt")
        github.comment_issue(
            issue,
            f"Die Lieferung wurde nicht abgeschlossen: [Actions-Lauf]({_actions_lauf_url()})",
        )
        return {"status": Status.LIEFERUNG_NICHT_ABGESCHLOSSEN}

    # Liefer-Tag am vorbereiteten Commit setzen, sobald Mainframe und GitHub-Release durch sind
    if subcommand == "tag":
        if parsed_tag is None or issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag oder Freigabe-Issue fehlt")
        return _erstelle_liefer_tag(parsed_tag, issue)

    # erfolgreichen Abschluss melden und gestartet durch abgeschlossen ersetzen
    if subcommand == "complete":
        if parsed_tag is None or issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag oder Freigabe-Issue fehlt")
        return _schliesse_freigabe(issue, parsed_tag)

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
