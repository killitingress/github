"""Liest Workflow-Läufe und veröffentlicht Releases über die GitHub-REST-API.

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


# Von GitHub für die REST-API vorgegebene Version des Anfrageformats.
_API_VERSION = "2022-11-28"

# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
_JSON_MEDIA_TYPE = "application/vnd.github+json"

# Gemeinsamer HTTP-Zugang zur GitHub-REST-API für alle Aufrufe dieses Moduls.
def request(
    *,
    method: str,
    url: str,
    token: str,
    failure: Status,
    payload: dict[str, object] | None = None,
    content: bytes | None = None,
    content_type: str | None = None,
    missing_ok: bool = False,
) -> Any:
    """Sendet eine Anfrage an GitHub und liest die JSON-Antwort.

    Bei einer fehlenden Ressource gibt die Funktion mit `missing_ok` `None`
    zurück. Andere HTTP- und Verbindungsfehler beenden den Schritt mit dem vom
    Aufrufer festgelegten Status.
    """

    # JSON oder Binärinhalt in den gemeinsamen GitHub-Request übernehmen
    body = json.dumps(payload).encode() if payload is not None else content
    headers = {
        "Accept": _JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    elif content_type is not None:
        headers["Content-Type"] = content_type

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

    repository = urllib.parse.quote(os.environ["GITHUB_REPOSITORY"])
    actions_url = f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{repository}/actions"
    parameters = {"branch": os.environ["GITHUB_REF_NAME"], "status": "success", "per_page": 1}
    if event:
        parameters["event"] = event

    query = urllib.parse.urlencode(parameters)
    url = f"{actions_url}/workflows/sync-resources.yml/runs?{query}"
    document = request(method="GET", url=url, token=os.environ["GITHUB_TOKEN"], failure=Status.SOURCE_FAILED)
    runs = document["workflow_runs"]
    return runs[0]["head_sha"] if runs else None


def _replace_information_files(
    information_files: list[Path],
    assets: dict[str, int],
    releases_url: str,
    upload_url: str,
    token: str,
) -> None:
    """Ersetzt die Informationsdateien eines GitHub Releases.

    GitHub kann den Inhalt eines Release-Anhangs nicht per PATCH ändern.
    Gleichnamige Dateien werden deshalb gelöscht und anschließend neu hochgeladen.
    """

    for information in information_files:
        # Datei erst unmittelbar vor ihrem Upload aus dem Release-Verzeichnis lesen
        try:
            content = information.read_bytes()
        except OSError as exc:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, f"Informationsdatei kann nicht gelesen werden: {information.name}: {exc}") from exc

        # vorhandenen Anhang entfernen, damit GitHub denselben Namen erneut annimmt
        if (asset_id := assets.get(information.name)) is not None:
            url = f"{releases_url}/assets/{asset_id}"
            request(method="DELETE", url=url, token=token, failure=Status.GITHUB_RELEASE_FAILED)

        # unveränderte JSON-Datei unter ihrem bisherigen Namen neu hochladen
        url = f"{upload_url}?{urllib.parse.urlencode({'name': information.name})}"
        request(method="POST", url=url, token=token, failure=Status.GITHUB_RELEASE_FAILED, content=content, content_type="application/json")


def run(tag: str) -> dict[str, object]:
    """Veröffentlicht den Lieferbericht und die erzeugten Informationsdateien.

    Ein vorhandenes Release wird aktualisiert. Gleichnamige, hier erzeugte
    Informationsdateien werden dabei ersetzt.
    """

    # GitHub-Ziel und erzeugte Informationsdateien des Releasebaus bestimmen
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    releases_url = f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{urllib.parse.quote(repository)}/releases"
    information_files = sorted((Path(os.environ["RUNNER_TEMP"]) / "release").glob("_INFO_*.json"))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

    # gemeinsamen Scope aus der ersten projektbezogenen Informationsdatei lesen
    try:
        scope = json.loads(information_files[0].read_text(encoding="utf-8"))["scope"]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, f"Informationsdatei kann nicht gelesen werden: {information_files[0].name}: {exc}") from exc
    delivery_type = "DELTA" if "von" in scope else "FULL"

    # sichtbaren Lieferbericht aus Tag, Lieferart und Ziel-Commit aufbauen
    release_values = {
        "tag_name": tag,
        "name": f"Release {tag}",
        "body": (
            "## Lieferung\n\n"
            f"- Liefer-Tag: `{tag}`\n"
            f"- Lieferart: `{delivery_type}`\n"
            f"- Commit: `{scope['bis']['commit']}`\n\n"
            "Die Archive und die zugehörige JCL wurden von FTPS und JES angenommen.\n"
        ),
        "draft": False,
        "prerelease": False,
    }

    # vorhandenes Release samt Anhängen lesen oder ein neues Release vorbereiten
    url = f"{releases_url}/tags/{urllib.parse.quote(tag, safe='')}"
    release = request(method="GET", url=url, token=token, failure=Status.GITHUB_RELEASE_FAILED, missing_ok=True)
    assets = {e["name"]: e["id"] for e in release["assets"]} if release is not None else {}

    # Lieferbericht durch Anlegen oder Aktualisieren veröffentlichen
    url = releases_url if release is None else f"{releases_url}/{release['id']}"
    method = "POST" if release is None else "PATCH"
    release = request(method=method, url=url, token=token, failure=Status.GITHUB_RELEASE_FAILED, payload=release_values)

    # URI-Vorlage auf den Upload-Endpunkt ohne GitHub-Platzhalter reduzieren
    upload_url = release["upload_url"].split("{", 1)[0]

    # Informationsdateien hochladen und gleichnamige Anhänge vorher ersetzen
    _replace_information_files(information_files, assets, releases_url, upload_url, token)

    # veröffentlichte Release-Adresse an den Workflow zurückgeben
    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED.value,
        "repository": repository,
        "liefer_tag": tag,
        "release_url": release["html_url"],
    }
