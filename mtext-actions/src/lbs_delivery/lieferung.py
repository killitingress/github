"""Bereitet Lieferungen vor, bestätigt sie und erzeugt Liefer-Tags."""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from . import config, git, github
from .process import DeliveryError, Status
from .project_archives import previous_release_scope, release_report, release_scope


# Name des GitHub-Actions-Artefakts mit der festgehaltenen Vorbereitung
_VORBEREITUNG_ARTEFAKT = "{tag}-lieferungsartefakt"


def _vorbereitungslauf(api_url: str, repository: str, tag: str, token: str) -> int | None:
    """Ermittelt den jüngsten verfügbaren Vorbereitungslauf zum Liefer-Tag."""

    # GitHub-Actions-Artefakte gezielt über den Namen dieser Lieferung abfragen
    repository_path = urllib.parse.quote(repository, safe="/")
    query = urllib.parse.urlencode({"name": _VORBEREITUNG_ARTEFAKT.format(tag=tag), "per_page": 100})
    url = f"{api_url.rstrip('/')}/repos/{repository_path}/actions/artifacts?{query}"
    document = github.request(method="GET", url=url, token=token, failure=Status.SOURCE_FAILED)

    # unerwartete GitHub-Antwort vor der Auswahl ablehnen
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakte können nicht ermittelt werden")

    # abgelaufene Vorbereitungen aus der möglichen Fortsetzung entfernen
    available = [
        e for e in document["artifacts"]
        if isinstance(e, dict) and e.get("expired") is False
    ]
    if not available:
        return None

    # jüngsten Lauf stabil nach Erstellungszeit und Artefakt-ID bestimmen
    try:
        newest = max(available, key=lambda artifact: (artifact["created_at"], artifact["id"]))
        return newest["workflow_run"]["id"]
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Vorbereitungsartefakt ist ungültig: {exc}") from exc


def _pruefe_lieferquelle(configuration: config.Configuration, root: Path, tag: str, branch: str, sha: str) -> None:
    """Prüft Liefer-Tag, Branch und ob der ausgewählte Branchstand noch aktuell ist."""

    # Liefer-Tag zerlegen und ungültige Formate vor allen Git-Zugriffen ablehnen
    tag_match = git.LIEFER_TAG_RE.fullmatch(tag)
    if tag_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, f"ungültiges Format des Liefer-Tags rnnn.nnn: {tag}")
    releaselinie = tag_match.group("releaselinie")
    zwischenrelease = tag_match.group("zwischenrelease")

    # neue Vorbereitung darf keinen bereits veröffentlichten Tag überschreiben
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist bereits vorhanden")

    # Bereitstellungsbranch oder regulären Branch der Releaselinie zuordnen
    bereitstellung = git.BEREITSTELLUNG_BRANCH_RE.fullmatch(branch)
    if bereitstellung is not None:
        if zwischenrelease == "100":
            raise DeliveryError(Status.VALIDATION_FAILED, ".100 entsteht nur auf main oder release/nnn")

        if bereitstellung.groups() != (releaselinie, zwischenrelease):
            raise DeliveryError(Status.SOURCE_FAILED, "Bereitstellungsbranch passt nicht zum Liefer-Tag")
    elif branch not in configuration.release_branches(releaselinie):
        raise DeliveryError(Status.SOURCE_FAILED, "Branch passt nicht zur Releaselinie")

    # Releaselinie muss in der gemeinsamen Zielzuordnung aktiv sein
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, f"Releaselinie {releaselinie} ist ungültig")

    # Vorbereitung nur für den weiterhin aktuellen Remote-Branchstand zulassen
    if git.resolve(root, f"refs/remotes/origin/{branch}") != sha:
        raise DeliveryError(Status.SOURCE_FAILED, "ausgewählter Branchstand ist nicht mehr aktuell")


def _summary(configuration: config.Configuration, root: Path, tag: str, branch: str, sha: str) -> str:
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

    # den gemeinsamen Lieferbericht aus den beiden Vergleichsumfängen erzeugen
    paket_scope = release_scope(root, tag, sha)
    information_scope = previous_release_scope(root, tag, sha)
    return "\n".join(lines) + "\n" + release_report(
        configuration, root, paket_scope=paket_scope, information_scope=information_scope,
    )


def _ermittle_lieferung(tag: str) -> dict[str, object]:
    """Ermittelt für `resolve` einen vorhandenen Tag oder die jüngste Vorbereitung."""

    # ungültige Tags vor dem Zugriff auf GitHub ablehnen
    if git.LIEFER_TAG_RE.fullmatch(tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Liefer-Tag")

    api_url = os.environ["GITHUB_API_URL"]
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    repository_path = urllib.parse.quote(repository, safe="/")
    tag_path = urllib.parse.quote(tag, safe="")
    url = f"{api_url.rstrip('/')}/repos/{repository_path}/git/ref/tags/{tag_path}"

    # vorhandener Liefer-Tag kennzeichnet einen Wiederanlauf
    reference = github.request(method="GET", url=url, token=token, failure=Status.SOURCE_FAILED, missing_ok=True)
    if reference is not None:
        return {"outputs": {"wiederholung": "true", "source_sha": reference["object"]["sha"]}}

    # neue Lieferung aus der jüngsten verfügbaren Vorbereitung fortsetzen
    run_id = _vorbereitungslauf(api_url, repository, tag, token)
    if run_id is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Für den Liefer-Tag besteht keine Vorbereitung")

    return {"outputs": {"wiederholung": "false", "vorbereitung_id": run_id,
                        "vorbereitung_name": _VORBEREITUNG_ARTEFAKT.format(tag=tag)}}


def _pruefe_lieferung(tag: str) -> dict[str, object]:
    """Hält für `check` den geprüften Branchstand und seinen Lieferumfang fest."""

    # aktuellen Mandantenstand einordnen und gegen Liefer-Tag und Branch prüfen
    source = config.mandant_source()
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["GITHUB_REF_NAME"]
    sha = git.resolve(source, "HEAD")
    actor = os.environ["GITHUB_ACTOR"]
    configuration = config.Configuration.load(source, repository)
    _pruefe_lieferquelle(configuration, source, tag, branch, sha)

    # geprüften Stand für Bestätigung und Tag-Erzeugung festhalten
    vorbereitung = config.workflow_workspace() / config.WORKFLOW_VORBEREITUNG_DATEI
    try:
        vorbereitung.write_text(
            json.dumps({"tag": tag, "sha": sha, "repository": repository, "prepare_actor": actor},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Vorbereitungsartefakt kann nicht geschrieben werden: {exc}") from exc

    # Vorbereitung und lesbare Vorprüfung an den Workflow übergeben
    return {
        "status": Status.LIEFERUNG_CHECKED.value,
        "summary": _summary(configuration, source, tag, branch, sha),
        "outputs": {"vorbereitung_path": vorbereitung.as_posix(),
                    "vorbereitung_name": _VORBEREITUNG_ARTEFAKT.format(tag=tag)},
    }


def _bestaetige_lieferung(expected_tag: str, confirm_direct_delivery: bool) -> dict[str, object]:
    """Bestätigt für `confirm` die festgehaltene Vorbereitung und ihren Lieferweg."""

    # Vorbereitung aus dem heruntergeladenen GitHub-Actions-Artefakt lesen
    vorbereitung = config.workflow_workspace() / "vorbereitung" / config.WORKFLOW_VORBEREITUNG_DATEI
    try:
        payload = json.loads(vorbereitung.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Vorbereitungsartefakt ist ungültig: {exc}") from exc

    # erwartete Angaben gemeinsam übernehmen oder das Artefakt ablehnen
    match payload:
        case {"tag": str(tag), "sha": str(sha), "repository": str(repository), "prepare_actor": str(prepare_actor)}:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig")

    # Vorbereitung dem aktuellen Repository und Liefer-Tag zuordnen
    if repository != os.environ["GITHUB_REPOSITORY"]:
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört zu einem anderen Repository")

    if tag != expected_tag:
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört zu einem anderen Liefer-Tag")

    # Direktlieferung nur nach bewusster Bestätigung zulassen
    direktlieferung = prepare_actor == os.environ["GITHUB_ACTOR"]
    if direktlieferung and not confirm_direct_delivery:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            "Direktlieferung muss mit der Abweichung vom empfohlenen 4-Augenprinzip und dem damit "
            "verbundenen Risiko bewusst bestätigt werden",
        )

    # bestätigten Commit und Lieferweg für die Folgeschritte ausgeben
    return {
        "status": Status.LIEFERUNG_BESTAETIGT.value,
        "summary": (
            "## Lieferung bestätigt\n\n"
            f"- Liefer-Tag: `{tag}`\n"
            f"- Commit: `{sha}`\n"
            f"- Lieferweg: {'Direktlieferung' if direktlieferung else '4-Augenfall'}\n"
        ),
        "outputs": {"source_sha": sha},
    }


def _erstelle_liefer_tag(tag: str) -> dict[str, object]:
    """Erzeugt für `tag` den Liefer-Tag auf dem ausgecheckten Commit."""

    # geprüften Checkout-Stand als neue GitHub-Referenz veröffentlichen
    repository = os.environ["GITHUB_REPOSITORY"]
    source_sha = git.resolve(config.mandant_source(), "HEAD")
    payload = {"ref": f"refs/tags/{tag}", "sha": source_sha}
    url = f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{urllib.parse.quote(repository, safe='/')}/git/refs"
    github.request(method="POST", url=url, token=os.environ["GITHUB_TOKEN"], failure=Status.SOURCE_FAILED, payload=payload)

    return {"status": Status.LIEFERUNG_TAGGED.value}


def run(subcommand: str, tag: str, confirm_direct_delivery: bool = False) -> dict[str, object]:
    """Führt das gewählte Lieferkommando über den einheitlichen Moduleinstieg aus."""

    if subcommand == "resolve":
        return _ermittle_lieferung(tag)

    if subcommand == "check":
        return _pruefe_lieferung(tag)

    if subcommand == "confirm":
        return _bestaetige_lieferung(tag, confirm_direct_delivery)

    if subcommand == "tag":
        return _erstelle_liefer_tag(tag)

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
