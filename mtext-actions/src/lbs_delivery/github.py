"""Liest Workflow-Läufe und veröffentlicht Releases über die GitHub-REST-API.

Header, Fehlerauswertung und die fachlichen GitHub-Aktionen liegen zusammen,
damit die Workflows einen gemeinsamen Weg zu GitHub verwenden.
"""

from __future__ import annotations

import argparse
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

    # Request-Body und Header für JSON oder Binärupload aufbauen.
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

    # Anfrage erstellen und ausführen
    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        # Antwort lesen
        with urllib.request.urlopen(http_request, timeout=NETWORK_TIMEOUT) as response:
            response_body = response.read()
    except urllib.error.HTTPError as ex:
        # Fehlende Ressourcen darf der Aufrufer als leeres Ergebnis behandeln.
        if missing_ok and ex.code == 404:
            return None

        # Fehlermeldung auslesen
        try:
            message = json.loads(ex.read()).get("message")
        except (UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
            message = None

        suffix = f": {message}" if isinstance(message, str) and message else ""
        raise DeliveryError(failure, f"GitHub antwortet mit HTTP {ex.code}{suffix}") from ex
    except (urllib.error.URLError, TimeoutError) as ex:
        raise DeliveryError(failure, "GitHub ist nicht erreichbar") from ex

    # Leere Antworten sind zulässig, ansonsten muss der Body gültiges JSON sein
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except (UnicodeError, json.JSONDecodeError) as ex:
        raise DeliveryError(failure, "GitHub-Antwort ist ungültig") from ex


def last_sync_commit(*, event: str | None = None) -> str | None:
    """Liest den Commit des jüngsten erfolgreichen Sync-Laufs dieses Branches.

    GitHub speichert den zum Lauf gehörenden Branchstand als `head_sha`.
    Die Abfrage dient als Vergleichsstand für das nächste DELTA. Beim Wechsel
    der Releaselinie auf main wird zusätzlich der erfolgreiche Push-Lauf
    benötigt, weil ein manueller Abgleich eine einzelne Zielstufe bedient.
    """

    repository = urllib.parse.quote(os.environ["GITHUB_REPOSITORY"])
    actions_url = f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{repository}/actions"
    parameters = {"branch": os.environ["GITHUB_REF_NAME"], "status": "success", "per_page": 1}
    if event:
        parameters["event"] = event

    query = urllib.parse.urlencode(parameters)
    document = request(
        method="GET",
        url=f"{actions_url}/workflows/sync-resources.yml/runs?{query}",
        token=os.environ["GITHUB_TOKEN"],
        failure=Status.SOURCE_FAILED,
    )
    runs = document["workflow_runs"]
    return runs[0]["head_sha"] if runs else None


def run(arguments: argparse.Namespace) -> dict[str, object]:
    """Veröffentlicht den Lieferbericht und die Informationsdateien aus dem Artefakt.

    Ein vorhandenes Release wird aktualisiert. Gleichnamige, hier erzeugte
    Informationsdateien werden dabei ersetzt.
    """

    repository = os.environ["GITHUB_REPOSITORY"]
    liefer_tag = arguments.tag
    token = os.environ["GITHUB_TOKEN"]
    releases_url = f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{urllib.parse.quote(repository)}/releases"
    information_files = sorted((Path(os.environ["RUNNER_TEMP"]) / "release").glob("_INFO_*.json"))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

    # Der Paketbau schreibt denselben Lieferstand in die Informationsdateien
    # aller Projekte. Die erste Datei liefert die Angaben für den Bericht.
    try:
        stand = json.loads(information_files[0].read_text(encoding="utf-8"))["stand"]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdatei kann nicht gelesen werden") from exc
    delivery_type = "DELTA" if "von" in stand else "FULL"

    # GitHub zeigt die hochgeladenen Informationsdateien als Release-Anhänge an.
    release_values = {
        "tag_name": liefer_tag,
        "name": f"Release {liefer_tag}",
        "body": (
            "## Lieferung\n\n"
            f"- Liefer-Tag: `{liefer_tag}`\n"
            f"- Lieferart: `{delivery_type}`\n"
            f"- Commit: `{stand['bis']['commit']}`\n\n"
            "Die Archive und die zugehörige JCL wurden von FTPS und JES angenommen.\n"
        ),
        "draft": False,
        "prerelease": False,
    }

    # Vorhandenes Release aktualisieren, sonst neu anlegen.
    release = request(
        method="GET",
        url=f"{releases_url}/tags/{urllib.parse.quote(liefer_tag, safe='')}",
        token=token,
        failure=Status.GITHUB_RELEASE_FAILED,
        missing_ok=True,
    )
    assets = {asset["name"]: asset["id"] for asset in release["assets"]} if release is not None else {}
    release = request(
        method="POST" if release is None else "PATCH",
        url=releases_url if release is None else f"{releases_url}/{release['id']}",
        token=token,
        failure=Status.GITHUB_RELEASE_FAILED,
        payload=release_values,
    )
    # GitHub liefert eine URI-Vorlage mit dem Suffix `{?name,label}`. Den
    # eigentlichen Query-String für den Dateinamen setzen wir beim Upload selbst.
    upload_url = release["upload_url"].split("{", 1)[0]

    # Informationsdateien als Release-Anhänge hochladen. PATCH auf Assets ändert nur
    # Name und Label, nicht den Dateiinhalt. Gleichnamige Anhänge lehnt GitHub beim
    # Upload ab, deshalb ersetzen wir sie bei einem Wiederanlauf per DELETE und POST.
    for information in information_files:
        try:
            content = information.read_bytes()
        except OSError as exc:
            raise DeliveryError(
                Status.GITHUB_RELEASE_FAILED, f"Informationsdatei kann nicht gelesen werden: {information.name}"
            ) from exc

        if (asset_id := assets.get(information.name)) is not None:
            request(
                method="DELETE", url=f"{releases_url}/assets/{asset_id}", token=token, failure=Status.GITHUB_RELEASE_FAILED
            )

        request(
            method="POST",
            url=f"{upload_url}?{urllib.parse.urlencode({'name': information.name})}",
            token=token,
            failure=Status.GITHUB_RELEASE_FAILED,
            content=content,
            content_type="application/json",
        )

    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED.value,
        "repository": repository,
        "liefer_tag": liefer_tag,
        "release_url": release["html_url"],
    }
