"""Bereitet Lieferungen vor, prüft ihre Freigabe und erzeugt Liefer-Tags."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config, git, github
from .process import DeliveryError, Status
from .project_packages import previous_release_scope, release_report, release_scope


# Name des GitHub-Actions-Artefakts für das zugehörige Freigabe-Issue
_VORBEREITUNG_ARTEFAKT = "lieferung-{issue}-vorbereitungsartefakt"

# Label zur fachlichen Kennzeichnung automatisch erzeugter Freigabe-Issues
_FREIGABE_LABEL = "lieferung:freigabe"

# Beschreibung des Labels in der Repository-Oberfläche
_FREIGABE_LABEL_BESCHREIBUNG = "Vorbereitete Mainframe-Lieferung wartet auf Freigabe"


def liefer_tag_fuer_branch(configuration: config.Configuration, branch: str) -> git.LieferTag:
    """Leitet den Liefer-Tag aus einem zulässigen Lieferzweig ab."""

    # Git-Namen auswerten, bevor die fachlichen Lieferregeln greifen
    tag = git.LieferTag.from_lieferzweig(branch, configuration.releaselinie)
    if tag is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Branch ist kein Lieferzweig")

    # .100 bezeichnet den Vollstand und darf nicht als Teillieferung entstehen
    if tag.ist_hauptrelease and git.LieferTag.from_bereitstellung(branch) is not None:
        raise DeliveryError(Status.VALIDATION_FAILED, ".100 entsteht auf main oder release/nnn")

    # Releaselinie muss in der gemeinsamen Zielzuordnung aktiv sein
    if tag.releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, f"Releaselinie {tag.releaselinie} ist ungültig")

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

    # den hübschen Lieferbericht aus den beiden Vergleichsumfängen erzeugen
    paket_scope = release_scope(root, tag, sha)
    information_scope = previous_release_scope(root, tag, sha)
    return "\n".join(lines) + "\n" + release_report(
        configuration, root, paket_scope=paket_scope, information_scope=information_scope,
    )


def _ermittle_lieferung(tag: git.LieferTag | None, issue: int | None) -> dict[str, object]:
    """Ermittelt für `resolve` einen vorhandenen Tag oder die freigegebene Vorbereitung."""

    # genau einer der beiden Lieferwege muss ausgewählt sein
    if (tag is None) == (issue is None):
        raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag oder Freigabe-Issue muss angegeben werden")

    # jede neue Lieferung und Wiederholung erfordert Maintain oder Admin
    role = github.repository_role(os.environ["GITHUB_ACTOR"])
    if role not in ("maintain", "admin"):
        raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe erfordert Repository-Berechtigung maintain oder admin")

    # offene und markierte Freigabe dem zugeordneten Artefakt zuweisen
    if issue is not None:
        state, labels = github.issue(issue)
        if state != "open" or _FREIGABE_LABEL not in labels:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue ist nicht offen oder nicht gekennzeichnet")

        artifact_id = github.latest_artifact(_VORBEREITUNG_ARTEFAKT.format(issue=issue))
        if artifact_id is None:
            raise DeliveryError(Status.SOURCE_FAILED, "Für das Freigabe-Issue besteht keine Vorbereitung")

        return {
            "status": Status.LIEFERSTAND_ERMITTELT,
            "outputs": {"wiederholung": "false", "vorbereitung_artefakt_id": artifact_id},
        }

    # ein manueller Aufruf ist ausschließlich für einen vorhandenen Liefer-Tag vorgesehen
    source_sha = github.tag_sha(str(tag))
    if source_sha is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Neue Lieferung muss über ihr Freigabe-Issue gestartet werden")

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


def _erstelle_freigabe_issue(tag: git.LieferTag, summary: str) -> tuple[int, str]:
    """Erstellt das Issue mit Lieferumfang und Bedienhinweis für die Freigabe."""

    # geprüften Bericht mit Urheber und Vorbereitungslauf im Issue zeigen
    body = (
        f"{summary}\n"
        "---\n\n"
        "## Freigabe\n\n"
        f"- Vorbereitet durch: @{os.environ['GITHUB_ACTOR']} ([Actions-Lauf]({_actions_lauf_url()}))\n\n"
        "Lieferung starten durch einen Kommentar, der ausschließlich `/freigabe` enthält.\n"
    )

    # Issue-Nummer bindet das spätere Laufartefakt an diese Freigabe
    return github.create_labeled_issue(
        title=f"Lieferung {tag} freigeben",
        body=body,
        label=_FREIGABE_LABEL,
        label_description=_FREIGABE_LABEL_BESCHREIBUNG,
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
    issue, issue_url = _erstelle_freigabe_issue(tag, summary)
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
        "summary": f"{summary}\n## Freigabe\n\n[Freigabe-Issue #{issue}]({issue_url})\n",
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

    # gestarteten Lauf im Issue verknüpfen, bevor die Verarbeitung in Folgejobs wechselt
    github.comment_issue(
        issue,
        f"Lieferung `{tag}` wurde gestartet: [Actions-Lauf]({_actions_lauf_url()})",
    )

    # bestätigten Commit und Liefer-Tag für die Folgeschritte ausgeben
    return {
        "status": Status.LIEFERUNG_BESTAETIGT,
        "summary": (
            "## Lieferung bestätigt\n\n"
            f"- Liefer-Tag: `{tag}`\n"
            f"- Commit: `{sha}`\n"
            f"- Freigegeben durch: `{os.environ['GITHUB_ACTOR']}`\n"
        ),
        "outputs": {"source_sha": sha, "liefer_tag": tag},
    }


def _schliesse_freigabe(issue: int, tag: git.LieferTag) -> dict[str, object]:
    """Dokumentiert die erfolgreiche Lieferung und schließt ihr Freigabe-Issue."""

    # Ergebnis und ausführenden Actions-Lauf im Freigabeprotokoll ergänzen
    github.complete_issue(
        issue,
        f"Lieferung `{tag}` wurde erfolgreich ausgeführt: [Actions-Lauf]({_actions_lauf_url()})",
    )
    return {"status": Status.LIEFERUNG_ABGESCHLOSSEN}


def _erstelle_liefer_tag(tag: git.LieferTag) -> dict[str, object]:
    """Erzeugt den Liefer-Tag auf der vorbereiteten Commit-SHA."""

    # identischen Tag aus einem wiederholten GitHub-Abschluss übernehmen
    source_sha = os.environ["SOURCE_SHA"]
    existing_sha = github.tag_sha(str(tag))
    if existing_sha is not None and existing_sha != source_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag zeigt auf einen anderen Commit")

    # fehlenden Tag direkt auf der bereits bekannten SHA anlegen
    if existing_sha is None:
        github.create_tag(str(tag), source_sha)

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

    # GitHub Actions verwendet 0 als technischen Standardwert für ein fehlendes Issue
    if issue == 0:
        issue = None

    if subcommand == "resolve":
        return _ermittle_lieferung(parsed_tag, issue)

    if subcommand == "check":
        if parsed_tag is not None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag wird aus dem Branch ermittelt")
        return _pruefe_lieferung()

    if subcommand == "confirm":
        if issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue fehlt")
        return _bestaetige_lieferung(issue)

    if subcommand == "incomplete":
        if issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-Issue fehlt")
        github.comment_issue(
            issue,
            f"Die Lieferung wurde nicht abgeschlossen: [Actions-Lauf]({_actions_lauf_url()})",
        )
        return {"status": Status.LIEFERUNG_NICHT_ABGESCHLOSSEN}

    if subcommand == "tag":
        if parsed_tag is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag fehlt")
        return _erstelle_liefer_tag(parsed_tag)

    if subcommand == "complete":
        if parsed_tag is None or issue is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag oder Freigabe-Issue fehlt")
        return _schliesse_freigabe(issue, parsed_tag)

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
