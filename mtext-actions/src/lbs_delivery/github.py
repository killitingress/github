"""Modul für die Kommunikation mit GitHub."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
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


def _request(
    *, method: str, url: str, failure: Status, payload: dict[str, object] | None = None,
    missing_errors: tuple[tuple[int, str | None], ...] = (),
) -> Any:
    """Sendet eine Anfrage und behandelt einen erwarteten HTTP-Fehler als fehlende Ressource."""

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
            # technische GitHub-Meldung für die Workflow-Diagnose erhalten
            try:
                detail = json.loads(ex.read())["message"]
            except (UnicodeError, json.JSONDecodeError, KeyError, TypeError):
                detail = ex.reason

            # Status und optionale GitHub-Meldung müssen das erwartete Fehlen belegen
            if (ex.code, None) in missing_errors or (ex.code, detail) in missing_errors:
                return None

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


def _reference_url(reference: str, *, collection: bool = False) -> str:
    """Baut die Lese- oder Änderungsadresse einer Git-Referenz."""
    path = urllib.parse.quote(reference.removeprefix("refs/"), safe="/")
    return _repository_url(f"git/{'refs' if collection else 'ref'}/{path}")


def _reference_object(reference: str) -> tuple[str, str] | None:
    """Liest Typ und SHA des Objekts hinter einer Git-Referenz."""
    document = _request(method="GET", url=_reference_url(reference), failure=Status.SOURCE_FAILED,
                        missing_errors=((404, None),))
    if document is None:
        return None

    match document:
        case {"object": {"type": str(object_type), "sha": str(sha)}}:
            return object_type, sha
    raise DeliveryError(Status.SOURCE_FAILED, "Git-Referenz ist ungültig")


def reference_commit(reference: str) -> str | None:
    """Gibt den Commit einer technischen Git-Referenz zurück, falls sie existiert."""
    target = _reference_object(reference)
    if target is None:
        return None

    object_type, sha = target
    if object_type != "commit":
        raise DeliveryError(Status.SOURCE_FAILED, "Git-Referenz zeigt nicht auf einen Commit")
    return sha


def create_reference(reference: str, sha: str) -> None:
    """Erzeugt eine technische Git-Referenz auf den angegebenen Commit."""
    payload = {"ref": reference, "sha": sha}
    _request(method="POST", url=_repository_url("git/refs"), failure=Status.SOURCE_FAILED, payload=payload)


def set_reference(reference: str, sha: str) -> None:
    """Erzeugt eine technische Git-Referenz oder setzt sie auf den neuen Commit."""
    # vorhandenen Stand direkt fortschreiben, ohne vorherige Leseanfrage und Zeitfenster
    updated = _request(method="PATCH", url=_reference_url(reference, collection=True),
                       failure=Status.SOURCE_FAILED, payload={"sha": sha, "force": True},
                       missing_errors=((404, None), (422, "Reference does not exist")))

    # GitHub kennzeichnet eine beim PATCH fehlende Referenz als nicht vorhanden
    if updated is None:
        create_reference(reference, sha)


def delete_reference(reference: str) -> None:
    """Entfernt eine vorhandene technische Git-Referenz."""
    _request(method="DELETE", url=_reference_url(reference, collection=True), failure=Status.SOURCE_FAILED,
             missing_errors=((404, None), (422, "Reference does not exist")))


def _label_names(labels: object) -> set[str]:
    """Liest die Labelnamen aus einer GitHub-Antwort."""

    if not isinstance(labels, list):
        return set()
    return {e["name"] for e in labels if isinstance(e, dict) and isinstance(e.get("name"), str)}


def _ensure_label(name: str, description: str) -> None:
    """Legt ein fachliches Label im Repository bei Bedarf an."""

    url = _repository_url(f"labels/{urllib.parse.quote(name, safe='')}")
    if _request(method="GET", url=url, failure=Status.FREIGABE_FAILED, missing_errors=((404, None),)) is None:
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


def open_labeled_issue(title: str, labels: tuple[str, ...]) -> int | None:
    """Sucht ein offenes Issue mit dem Titel und einem der angegebenen Labels."""
    # je Status-Label abfragen, weil GitHub mehrere Labels als UND verknüpft
    for label in labels:
        query = urllib.parse.urlencode({"state": "open", "labels": label, "per_page": 100})
        documents = _request(method="GET", url=f"{_repository_url('issues')}?{query}", failure=Status.FREIGABE_FAILED)
        if not isinstance(documents, list):
            raise DeliveryError(Status.FREIGABE_FAILED, "GitHub liefert keine gültige Issue-Liste zurück")

        # Pull Requests stehen ebenfalls in der Issue-Liste und zählen hier nicht
        for document in documents:
            if isinstance(document, dict) and document.get("title") == title and "pull_request" not in document:
                number = document.get("number")
                if isinstance(number, int):
                    return number
    return None


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

    target = _reference_object(f"refs/tags/{tag}")
    if target is None:
        return None

    # Liefer-Tags tragen die Issue-Zuordnung in ihrem annotierten Tag-Inhalt
    object_type, tag_sha = target
    if object_type != "tag":
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist nicht annotiert")
    document = _request(method="GET", url=_repository_url(f"git/tags/{tag_sha}"), failure=Status.SOURCE_FAILED)

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

    # Tag-Inhalt prüfen und über denselben Ref-Adapter wie technische Stände benennen
    match document:
        case {"sha": str(tag_sha)}:
            create_reference(f"refs/tags/{tag}", tag_sha)
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
