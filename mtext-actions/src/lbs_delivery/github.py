"""Liest Workflow-Läufe, Issues, Artefakte, Tags und Rollen und veröffentlicht Releases.

Header, Fehlerauswertung und die fachlichen GitHub-Aktionen liegen zusammen,
damit die Workflows einen gemeinsamen Weg zu GitHub verwenden.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .project_packages import INFORMATION_PATTERN, RELEASE_REPORT_NAME


# Von GitHub für die REST-API vorgegebene Version des Anfrageformats.
_API_VERSION = "2022-11-28"

# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
_JSON_MEDIA_TYPE = "application/vnd.github+json"


def _repository_url(path: str) -> str:
    """Baut die REST-Adresse einer Ressource im aktuellen Repository."""

    repository = urllib.parse.quote(os.environ["GITHUB_REPOSITORY"], safe="/")
    return f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{repository}/{path}"


def _request(*, method: str, url: str, failure: Status, payload: dict[str, object] | bytes | None = None, missing_ok: bool = False) -> Any:
    """Sendet eine Anfrage an GitHub und liest die JSON-Antwort.

    Bei einer fehlenden Ressource (404) gibt die Funktion mit `missing_ok`
    `None` zurück. Andere HTTP- und Verbindungsfehler beenden den Schritt mit
    dem vom Aufrufer festgelegten Status.
    """

    # JSON oder Binärinhalt in den gemeinsamen GitHub-Request übernehmen
    body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
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


def last_sync_commit(*, event: str | None = None) -> str | None:
    """Liest den Commit des jüngsten erfolgreichen Sync-Laufs dieses Branches.

    GitHub speichert den zum Lauf gehörenden Branchstand als `head_sha`.
    Die Abfrage dient als Vergleichsstand für das nächste DELTA. Beim Wechsel
    der Releaselinie auf main wird zusätzlich der erfolgreiche Push-Lauf
    benötigt, weil ein manueller Abgleich eine einzelne Umgebung bedient.
    """

    parameters = {"branch": os.environ["GITHUB_REF_NAME"], "status": "success", "per_page": 1}
    if event:
        parameters["event"] = event

    query = urllib.parse.urlencode(parameters)
    url = f"{_repository_url('actions/workflows/sync-resources.yml/runs')}?{query}"
    document = _request(method="GET", url=url, failure=Status.SOURCE_FAILED)
    runs = document["workflow_runs"]
    return runs[0]["head_sha"] if runs else None


def _label_names(document: dict[str, object]) -> set[str]:
    """Liest die Labelnamen aus einer GitHub-Issue-Antwort."""

    labels = document.get("labels")
    if not isinstance(labels, list):
        return set()
    return {
        e.get("name") for e in labels
        if isinstance(e, dict) and isinstance(e.get("name"), str)
    }


def create_labeled_issue(*, title: str, body: str, labels: dict[str, str]) -> tuple[int, str]:
    """Erstellt bei Bedarf die Labels und danach das damit markierte Issue."""

    # fachliche Labels bei der ersten Verwendung im Repository anlegen
    for label, description in labels.items():
        url = _repository_url(f"labels/{urllib.parse.quote(label, safe='')}")
        existing_label = _request(method="GET", url=url, failure=Status.FREIGABE_FAILED, missing_ok=True)
        if existing_label is None:
            payload = {"name": label, "color": "1f883d", "description": description}
            _request(method="POST", url=_repository_url("labels"), failure=Status.FREIGABE_FAILED, payload=payload)

    # das Issue erhält die nun vorhandenen Labels bereits beim Anlegen
    payload = {"title": title, "body": body, "labels": list(labels)}
    document = _request(method="POST", url=_repository_url("issues"), failure=Status.FREIGABE_FAILED, payload=payload)
    if not isinstance(document, dict):
        raise DeliveryError(Status.FREIGABE_FAILED, "GitHub liefert kein Freigabe-Issue zurück")

    # fehlende Label-Berechtigung darf kein nicht freigebbares Issue hinterlassen
    if not labels.keys() <= _label_names(document):
        raise DeliveryError(Status.FREIGABE_FAILED, "GitHub hat nicht alle Freigabe-Labels gesetzt")

    # Nummer und HTML-Adresse an den Lieferablauf übergeben
    match document:
        case {"number": int(number), "html_url": str(html_url)}:
            return number, html_url
        case _:
            raise DeliveryError(Status.FREIGABE_FAILED, "Freigabe-Issue ist ungültig")


def issue(number: int) -> tuple[str, set[str]]:
    """Gibt Status und Labelnamen eines Issues aus dem aktuellen Repository zurück."""

    document = _request(method="GET", url=_repository_url(f"issues/{number}"), failure=Status.FREIGABE_FAILED)
    match document:
        case {"state": str(state)}:
            return state, _label_names(document)
        case _:
            raise DeliveryError(Status.FREIGABE_FAILED, "GitHub liefert kein Freigabe-Issue zurück")


def repository_role(username: str) -> str | None:
    """Ermittelt die wirksame Repository-Rolle einer Person."""

    actor = urllib.parse.quote(username, safe="")
    url = _repository_url(f"collaborators/{actor}/permission")
    document = _request(method="GET", url=url, failure=Status.FREIGABE_FAILED)

    return document.get("role_name") if isinstance(document, dict) else None


def latest_artifact(name: str) -> int | None:
    """Ermittelt die ID des jüngsten nicht abgelaufenen Artefakts dieses Namens."""

    query = urllib.parse.urlencode({"name": name, "per_page": 100})
    url = f"{_repository_url('actions/artifacts')}?{query}"
    document = _request(method="GET", url=url, failure=Status.SOURCE_FAILED)

    # unerwartete GitHub-Antwort vor der Auswahl ablehnen
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise DeliveryError(Status.SOURCE_FAILED, "Artefakte können nicht ermittelt werden")

    # abgelaufene Artefakte aus der möglichen Fortsetzung entfernen
    available = [
        e for e in document["artifacts"]
        if isinstance(e, dict) and e.get("expired") is False
    ]
    if not available:
        return None

    # jüngstes Artefakt stabil nach Erstellungszeit und Artefakt-ID bestimmen
    try:
        newest = max(available, key=lambda artifact: (artifact["created_at"], artifact["id"]))
        return newest["id"]
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Artefakt ist ungültig: {exc}") from exc


def tag_sha(tag: str) -> str | None:
    """Liest die Commit-SHA eines Tags oder None, wenn der Tag fehlt."""

    url = _repository_url(f"git/ref/tags/{urllib.parse.quote(tag, safe='')}")
    reference = _request(method="GET", url=url, failure=Status.SOURCE_FAILED, missing_ok=True)

    if reference is None:
        return None

    return reference["object"]["sha"]


def create_tag(tag: str, sha: str) -> None:
    """Erzeugt eine Git-Tag-Referenz auf dem angegebenen Commit."""

    url = _repository_url("git/refs")
    _request(method="POST", url=url, failure=Status.SOURCE_FAILED, payload={"ref": f"refs/tags/{tag}", "sha": sha})


def comment_issue(number: int, body: str) -> None:
    """Ergänzt einen Kommentar im angegebenen Issue."""

    issue_url = _repository_url(f"issues/{number}")
    url = f"{issue_url}/comments"
    _request(method="POST", url=url, failure=Status.FREIGABE_FAILED, payload={"body": body})


def complete_issue(number: int, body: str) -> None:
    """Ergänzt das Ergebnis und schließt das Issue im aktuellen Repository."""

    # erfolgreichen Lauf im Freigabeprotokoll ergänzen
    comment_issue(number, body)

    # abgeschlossenes Issue als weiterhin lesbares Protokoll erhalten
    issue_url = _repository_url(f"issues/{number}")
    _request(method="PATCH", url=issue_url, failure=Status.FREIGABE_FAILED, payload={"state": "closed"})


def _replace_information_files(files: list[Path], assets: dict[str, int], upload_url: str) -> None:
    """Ersetzt die Informationsdateien eines GitHub Releases.

    GitHub kann den Inhalt eines Release-Anhangs nicht per PATCH ändern.
    Gleichnamige Dateien werden deshalb gelöscht und anschließend neu hochgeladen.
    """

    for information in files:
        # Datei erst unmittelbar vor ihrem Upload aus dem Release-Verzeichnis lesen
        try:
            content = information.read_bytes()
        except OSError as exc:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, f"Informationsdatei kann nicht gelesen werden: {information.name}: {exc}") from exc

        # vorhandenen Anhang entfernen, damit GitHub denselben Namen erneut annimmt
        if (asset_id := assets.get(information.name)) is not None:
            url = _repository_url(f"releases/assets/{asset_id}")
            _request(method="DELETE", url=url, failure=Status.GITHUB_RELEASE_FAILED)

        # unveränderte JSON-Datei unter ihrem bisherigen Namen neu hochladen
        url = f"{upload_url}?{urllib.parse.urlencode({'name': information.name})}"
        _request(method="POST", url=url, failure=Status.GITHUB_RELEASE_FAILED, payload=content)


def run(tag: str) -> dict[str, object]:
    """Veröffentlicht den Lieferbericht und die erzeugten Informationsdateien.

    Ein vorhandenes Release wird aktualisiert. Gleichnamige, hier erzeugte
    Informationsdateien werden dabei ersetzt.
    """

    # GitHub-Ziel und erzeugte Informationsdateien des Releasebaus bestimmen
    repository = os.environ["GITHUB_REPOSITORY"]
    releases_url = _repository_url("releases")
    information_files = sorted((Path(os.environ["RUNNER_TEMP"]) / "release").glob(INFORMATION_PATTERN))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

    # der beim Paketbau erstellte Bericht enthält Vorrelease-Diff und Lieferumfang
    try:
        report = (Path(os.environ["RUNNER_TEMP"]) / "release" / RELEASE_REPORT_NAME).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, f"Lieferbericht kann nicht gelesen werden: {exc}") from exc

    # Release kennzeichnet eine übersprungene Mainframe-Übergabe sichtbar
    dry_run = os.environ.get("DRY_RUN") == "true"
    confirmation = (
        "Dry Run: FTPS- und JES-Übergabe wurden übersprungen.\n"
        if dry_run
        else "Die Archive und die zugehörige JCL wurden von FTPS und JES angenommen.\n"
    )

    # nach der Übergabe beide Dateilisten direkt im GitHub Release veröffentlichen
    release_values = {
        "tag_name": tag,
        "name": f"{'Dry Run ' if dry_run else 'Release '}{tag}",
        "body": report + "\n" + confirmation,
        "draft": False,
        "prerelease": dry_run,
    }

    # vorhandenes Release samt Anhängen lesen oder ein neues Release vorbereiten
    url = f"{releases_url}/tags/{urllib.parse.quote(tag, safe='')}"
    release = _request(method="GET", url=url, failure=Status.GITHUB_RELEASE_FAILED, missing_ok=True)
    assets = {e["name"]: e["id"] for e in release["assets"]} if release is not None else {}

    # Lieferbericht durch Anlegen oder Aktualisieren veröffentlichen
    url = releases_url if release is None else f"{releases_url}/{release['id']}"
    method = "POST" if release is None else "PATCH"
    release = _request(method=method, url=url, failure=Status.GITHUB_RELEASE_FAILED, payload=release_values)

    # URI-Vorlage auf den Upload-Endpunkt ohne GitHub-Platzhalter reduzieren
    upload_url = release["upload_url"].split("{", 1)[0]

    # Informationsdateien hochladen und gleichnamige Anhänge vorher ersetzen
    _replace_information_files(information_files, assets, upload_url)

    # veröffentlichte Release-Adresse an den Workflow zurückgeben
    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED,
        "repository": repository,
        "liefer_tag": tag,
        "release_url": release["html_url"],
        "dry_run": dry_run,
    }
