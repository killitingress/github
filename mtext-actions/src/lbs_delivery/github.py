"""Liest Pull Requests und veröffentlicht Releases über die GitHub-REST-API.

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
API_VERSION = "2022-11-28"

# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
JSON_MEDIA_TYPE = "application/vnd.github+json"


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

    body = json.dumps(payload).encode() if payload is not None else content
    headers = {
        "Accept": JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    elif content_type is not None:
        headers["Content-Type"] = content_type

    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(http_request, timeout=NETWORK_TIMEOUT) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        detail = ""
        try:
            error_body = json.loads(exc.read())
        except (UnicodeError, json.JSONDecodeError):
            pass
        else:
            if isinstance(error_body, dict) and isinstance(error_body.get("message"), str):
                detail = error_body["message"]
        suffix = f": {detail}" if detail else ""
        raise DeliveryError(failure, f"GitHub antwortet mit HTTP {exc.code}{suffix}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeliveryError(failure, "GitHub ist nicht erreichbar") from exc

    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(failure, "GitHub-Antwort ist ungültig") from exc


def read_pull_request(*, api_url: str, repository: str, number: int, token: str) -> dict[str, object]:
    """Liest den gemergten Pull Request als Grundlage der Freigabeprüfung."""

    document = request(
        method="GET",
        url=f"{api_url.rstrip('/')}/repos/{urllib.parse.quote(repository, safe='/')}/pulls/{number}",
        token=token,
        failure=Status.SOURCE_FAILED,
    )
    if not isinstance(document, dict):
        raise DeliveryError(Status.SOURCE_FAILED, "GitHub-Antwort zum Pull Request ist ungültig")
    return document


def publish_release(
    *,
    artifact_root: str | Path,
    api_url: str,
    server_url: str,
    repository: str,
    release_tag: str,
    source_sha: str,
    token: str,
) -> dict[str, object]:
    """Legt das GitHub Release an und hängt die Informationsdateien an.

    Ein vorhandenes Release wird aktualisiert. Gleichnamige, hier erzeugte
    Informationsdateien werden dabei ersetzt.
    """

    information_files = sorted(Path(artifact_root).glob("_INFO_*.json"))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

    # Die Informationsdateien bestimmen die gemeinsame Lieferart des Releases.
    delivery_types: set[str] = set()
    try:
        for information in information_files:
            document = json.loads(information.read_text(encoding="utf-8"))
            delivery_types.add("DELTA" if "von" in document["stand"] else "FULL")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdatei ist ungültig") from exc
    if len(delivery_types) != 1:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien haben verschiedene Lieferarten")
    delivery_type = delivery_types.pop()

    # Die Release-Beschreibung verlinkt auf die hochgeladenen Informationsdateien.
    download_root = f"{server_url.rstrip('/')}/{repository}/releases/download/{urllib.parse.quote(release_tag, safe='')}"
    lines = [
        "## Lieferung",
        "",
        f"- Release: `{release_tag}`",
        f"- Lieferart: `{delivery_type}`",
        f"- Commit: `{source_sha}`",
        "",
        "Die Pakete und die zugehörige JCL wurden von FTPS und JES angenommen.",
        "",
        "## Informationsdateien",
        "",
    ]
    for information in information_files:
        name = information.name
        lines.append(f"- [Herunterladen]({download_root}/{urllib.parse.quote(name, safe='')}): `{name}`")
    release_values = {
        "tag_name": release_tag,
        "name": f"Release {release_tag}",
        "body": "\n".join(lines) + "\n",
        "draft": False,
        "prerelease": False,
    }
    repository_path = urllib.parse.quote(repository)
    release_path = urllib.parse.quote(release_tag, safe="")
    releases_url = f"{api_url.rstrip('/')}/repos/{repository_path}/releases"

    # Ein vorhandenes Release wird aktualisiert, ein fehlendes wird neu angelegt.
    release = request(
        method="GET",
        url=f"{releases_url}/tags/{release_path}",
        token=token,
        failure=Status.GITHUB_RELEASE_FAILED,
        missing_ok=True,
    )
    existing_assets: list[dict[str, Any]] = []
    if release is None:
        release = request(
            method="POST", url=releases_url, token=token, failure=Status.GITHUB_RELEASE_FAILED, payload=release_values
        )
    else:
        match release:
            case {"id": int(release_id), "assets": list(existing_assets)}:
                pass
            case _:
                raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Vorhandenes GitHub Release ist ungültig")
        release = request(
            method="PATCH",
            url=f"{releases_url}/{release_id}",
            token=token,
            failure=Status.GITHUB_RELEASE_FAILED,
            payload=release_values,
        )

    # Die API bestimmt Upload-Adresse und sichtbare Release-Adresse.
    match release:
        case {"upload_url": str(upload_url), "html_url": str(release_url)}:
            upload_url = upload_url.split("{", 1)[0]
        case _:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub Release ist unvollständig")

    # Eigene Informationsdateien eines Wiederanlaufs werden vor dem Upload ersetzt.
    assets_by_name: dict[str, int] = {}
    for asset in existing_assets:
        match asset:
            case {"name": str(name), "id": int(asset_id)}:
                assets_by_name[name] = asset_id
            case _:
                raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub-Asset ist ungültig")
    for information in information_files:
        name = information.name
        if (asset_id := assets_by_name.get(name)) is not None:
            request(
                method="DELETE", url=f"{releases_url}/assets/{asset_id}", token=token, failure=Status.GITHUB_RELEASE_FAILED
            )
        request(
            method="POST",
            url=f"{upload_url}?{urllib.parse.urlencode({'name': name})}",
            token=token,
            failure=Status.GITHUB_RELEASE_FAILED,
            content=information.read_bytes(),
            content_type="application/json",
        )

    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED.value,
        "repository": repository,
        "release_tag": release_tag,
        "release_url": release_url,
    }


def run_publish_command(_arguments: argparse.Namespace) -> dict[str, object]:
    """Veröffentlicht die Lieferinformationen aus dem Workflow-Arbeitsbereich."""

    return publish_release(
        artifact_root=Path(os.environ["RELEASE_DIRECTORY"]),
        api_url=os.environ["GITHUB_API_URL"],
        server_url=os.environ["GITHUB_SERVER_URL"],
        repository=os.environ["SOURCE_REPOSITORY"],
        release_tag=os.environ["RELEASE_TAG"],
        source_sha=os.environ["TRIGGER_SHA"],
        token=os.environ["MANDANT_REPOSITORY_TOKEN"],
    )
