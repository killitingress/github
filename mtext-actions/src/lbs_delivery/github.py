"""Modul für die Kommunikation mit GitHub."""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Any

from .process import DeliveryError, NETWORK_TIMEOUT, Status


# Von GitHub für die REST-API vorgegebene Version des Anfrageformats.
_API_VERSION = "2022-11-28"

# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
_JSON_MEDIA_TYPE = "application/vnd.github+json"

# Präfix der festen Issue-Zuordnung im annotierten Liefer-Tag
_TAG_ISSUE_PREFIX = "Freigabe-Issue: #"


def _repository_url(path: str) -> str:
    """Baut die REST-Adresse einer Ressource im aktuellen Repository."""

    repository = urllib.parse.quote(os.environ["GITHUB_REPOSITORY"], safe="/")
    return f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{repository}/{path}"


def _request(*, method: str, url: str, failure: Status, payload: dict[str, object] | None = None, missing_ok: bool = False) -> Any:
    """Sendet eine Anfrage an GitHub und liest die JSON-Antwort.

    Bei einer fehlenden Ressource (404) gibt die Funktion mit `missing_ok`
    `None` zurück. Andere HTTP- und Verbindungsfehler beenden den Schritt mit
    dem vom Aufrufer festgelegten Status.
    """

    # JSON-Inhalt in den gemeinsamen GitHub-Request übernehmen
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Accept": _JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"

    # authentifizierte Anfrage mit festem API-Format erstellen
    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)

    # Antwort lesen und GitHub-Fehler in den Status des Aufrufers übersetzen
    try:
        with urllib.request.urlopen(http_request, timeout=NETWORK_TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as ex:
        with ex:
            # fehlende Ressourcen darf der Aufrufer als leeres Ergebnis behandeln
            if missing_ok and ex.code == 404:
                return None

            # technische GitHub-Meldung für die Workflow-Diagnose erhalten
            try:
                detail = json.loads(ex.read())["message"]
            except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
                detail = ex.reason
            raise DeliveryError(failure, f"GitHub antwortet mit HTTP {ex.code}: {detail}") from ex
    except (urllib.error.URLError, TimeoutError) as ex:
        raise DeliveryError(failure, f"GitHub ist nicht erreichbar: {ex}") from ex

    # leere Antwort oder geparstes JSON an den fachlichen Aufrufer zurückgeben
    if not body:
        return None
    try:
        return json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as ex:
        raise DeliveryError(failure, f"GitHub-Antwort ist ungültig: {ex}") from ex


def artifacts(name: str) -> list[dict[str, Any]]:
    """Liefert die neuesten Artefakte mit diesem Namen."""

    query = urllib.parse.urlencode({"name": name, "per_page": 100})
    return _request(
        method="GET", url=f"{_repository_url('actions/artifacts')}?{query}", failure=Status.SOURCE_FAILED,
    )["artifacts"]


def artifact_document(artifact_id: int, filename: str) -> Any:
    """Lädt eine JSON-Datei aus einem Artefakt, ohne das Archiv ins Dateisystem zu entpacken.

    Die Download-Grenze trennt den authentifizierten API-Aufruf vom signierten
    Speicherlink, damit das GitHub-Token nicht an den Speicherdienst gelangt.
    """

    # die API liefert eine kurzlebige Download-Adresse als Redirect
    request = urllib.request.Request(
        _repository_url(f"actions/artifacts/{artifact_id}/zip"),
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                 "Accept": _JSON_MEDIA_TYPE, "X-GitHub-Api-Version": _API_VERSION},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        try:
            with opener.open(request, timeout=NETWORK_TIMEOUT) as response:
                archive = response.read()
        except urllib.error.HTTPError as redirect:
            with redirect:
                if redirect.code != 302:
                    raise
                location = redirect.headers["Location"]
            with urllib.request.urlopen(location, timeout=NETWORK_TIMEOUT) as response:
                archive = response.read()

        # die benannte Datei lesen, JSON- und Archivfehler an dieser I/O-Grenze melden
        with zipfile.ZipFile(io.BytesIO(archive)) as document:
            return json.loads(document.read(filename))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"GitHub-Artefakt kann nicht gelesen werden: {exc}") from exc


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hält Download-Redirects an der authentifizierten API-Grenze an."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Überlässt die Weiterleitung dem Aufrufer ohne Übernahme der Zugangsdaten."""
        return None


def _label_names(labels: object) -> set[str]:
    """Liest die Labelnamen aus einer GitHub-Antwort."""

    if not isinstance(labels, list):
        return set()
    return {e["name"] for e in labels if isinstance(e, dict) and isinstance(e.get("name"), str)}


def _ensure_label(name: str, description: str) -> None:
    """Legt ein fachliches Label im Repository bei Bedarf an."""

    url = _repository_url(f"labels/{urllib.parse.quote(name, safe='')}")
    if _request(method="GET", url=url, failure=Status.FREIGABE_FAILED, missing_ok=True) is None:
        payload = {"name": name, "color": "1f883d", "description": description}
        _request(method="POST", url=_repository_url("labels"), failure=Status.FREIGABE_FAILED, payload=payload)


def create_labeled_issue(*, title: str, body: str, labels: dict[str, str]) -> int:
    """Erstellt bei Bedarf die Labels und danach das damit markierte Issue."""

    # fachliche Labels bei der ersten Verwendung im Repository anlegen
    for label, description in labels.items():
        _ensure_label(label, description)

    # das Issue erhält die nun vorhandenen Labels bereits beim Anlegen
    payload = {"title": title, "body": body, "labels": list(labels)}
    document = _request(method="POST", url=_repository_url("issues"), failure=Status.FREIGABE_FAILED, payload=payload)

    # fehlende Label-Berechtigung darf kein nicht freigebbares Issue hinterlassen
    if labels.keys() - _label_names(document.get("labels")):
        raise DeliveryError(Status.FREIGABE_FAILED, "GitHub hat nicht alle Freigabe-Labels gesetzt")

    # Issue-Nummer an den Lieferablauf übergeben
    match document:
        case {"number": int(number)}:
            return number
        case _:
            raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue ist ungültig")


def issue(number: int) -> tuple[str, set[str], str, str]:
    """Gibt Status, Labels, Titel und Text eines Issues im aktuellen Repository zurück."""

    document = _request(method="GET", url=_repository_url(f"issues/{number}"), failure=Status.FREIGABE_FAILED)
    match document:
        case {"state": str(state), "title": str(title)}:
            # GitHub liefert bei einem Issue ohne Text null
            body = document.get("body") or ""
            if not isinstance(body, str):
                raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue enthält keinen gültigen Text")
            return state, _label_names(document.get("labels")), title, body
        case _:
            raise DeliveryError(Status.FREIGABE_FAILED, "GitHub liefert kein Freigabe-Issue zurück")


def repository_role(username: str) -> str | None:
    """Ermittelt die wirksame Repository-Rolle einer Person."""

    actor = urllib.parse.quote(username, safe="")
    url = _repository_url(f"collaborators/{actor}/permission")
    document = _request(method="GET", url=url, failure=Status.FREIGABE_FAILED)
    return document.get("role_name")


def tag_record(tag: str) -> tuple[str, int] | None:
    """Liest Commit-SHA und Freigabe-Issue eines Liefer-Tags."""

    url = _repository_url(f"git/ref/tags/{urllib.parse.quote(tag, safe='')}")
    reference = _request(method="GET", url=url, failure=Status.SOURCE_FAILED, missing_ok=True)
    if reference is None:
        return None

    # Liefer-Tags tragen die Issue-Zuordnung in ihrem annotierten Tag-Inhalt
    match reference:
        case {"object": {"type": "tag", "sha": str(tag_sha)}}:
            document = _request(method="GET", url=_repository_url(f"git/tags/{tag_sha}"), failure=Status.SOURCE_FAILED)
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist nicht annotiert")

    match document:
        case {"tag": str(name), "message": str(message), "object": {"type": "commit", "sha": str(sha)}} if (
            name == tag and message.startswith(_TAG_ISSUE_PREFIX)
        ):
            issue_text = message.strip().removeprefix(_TAG_ISSUE_PREFIX)
            if issue_text.isdecimal() and (issue_number := int(issue_text)) > 0:
                return sha, issue_number

    # Fehler wenn der Tag keine gültige Zuordnung zu einem Freigabe-Issue hat
    raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag enthält keine gültige Freigabe-Issue-Zuordnung")


def create_tag(tag: str, sha: str, issue: int) -> None:
    """Erzeugt einen annotierten Liefer-Tag mit Freigabe-Issue und Commit."""

    # zuerst den Tag-Inhalt mit seiner festen Issue-Zuordnung anlegen
    payload = {"tag": tag, "message": f"{_TAG_ISSUE_PREFIX}{issue}", "object": sha, "type": "commit"}
    document = _request(method="POST", url=_repository_url("git/tags"), failure=Status.SOURCE_FAILED, payload=payload)

    # prüft ob der Tag-Inhalt erfolgreich erstellt wurde und erstellt die Git-Referenz
    match document:
        case {"sha": str(tag_sha)}:
            payload = {"ref": f"refs/tags/{tag}", "sha": tag_sha}
            _request(method="POST", url=_repository_url("git/refs"), failure=Status.SOURCE_FAILED, payload=payload)
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "GitHub liefert keinen Tag-Inhalt zurück")


def comment_issue(number: int, body: str) -> None:
    """Ergänzt einen Kommentar im angegebenen Issue."""

    issue_url = _repository_url(f"issues/{number}")
    _request(method="POST", url=f"{issue_url}/comments", failure=Status.FREIGABE_FAILED, payload={"body": body})


def complete_issue(number: int, body: str, started_label: str, completed_label: str, description: str) -> None:
    """Dokumentiert den Erfolg, kennzeichnet den Abschluss und schließt das Issue."""

    # erfolgreichen Lauf im Freigabeprotokoll ergänzen
    comment_issue(number, body)

    # erst nach dem Kommentar den erfolgreichen Status setzen
    replace_issue_label(number, started_label, completed_label, description, accept_existing=True)

    # abgeschlossenes Issue als weiterhin lesbares Protokoll erhalten
    issue_url = _repository_url(f"issues/{number}")
    _request(method="PATCH", url=issue_url, failure=Status.FREIGABE_FAILED, payload={"state": "closed"})


def replace_issue_label(number: int, old_label: str, new_label: str, description: str, *, accept_existing: bool = False) -> None:
    """Ersetzt ein Status-Label und erhält weitere Kennzeichen des Issues."""

    # vorhandene Kennzeichen wie dry_run für den Statuswechsel erhalten
    _ensure_label(new_label, description)
    _, labels, _, _ = issue(number)
    if old_label not in labels:
        # wiederholter Abschluss behält den bereits erreichten Status
        if accept_existing and new_label in labels:
            return
        raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue hat nicht das erwartete Status-Label")

    # bisherigen Status ersetzen, andere Kennzeichen wie dry_run erhalten
    labels = (labels - {old_label}) | {new_label}

    # alle Issue-Labels in einem Aufruf setzen und die Antwort prüfen
    issue_labels_url = _repository_url(f"issues/{number}/labels")
    payload = {"labels": sorted(labels)}
    assigned = _request(method="PUT", url=issue_labels_url, failure=Status.FREIGABE_FAILED, payload=payload)

    if _label_names(assigned) != labels:
        raise DeliveryError(Status.FREIGABE_FAILED, "Label setzen am Issue fehlgeschlagen")
