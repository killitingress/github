"""Veröffentlicht die Rückmeldung zu einer Mainframe-Lieferung in GitHub.

Nach der erfolgreichen FTPS-/JES-Übergabe entsteht im Mandanten-Repository ein
GitHub Release. Seine Beschreibung fasst die Lieferung zusammen. Die beim
Paketbau erzeugten JSON-Informationsdateien werden als Downloads angehängt.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

from . import github_api
from .process import DeliveryError, Status


def publish_github_release(
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

    Ein bereits vorhandenes Release wird aktualisiert. Gleichnamige, von diesem
    Ablauf erzeugte Informationsdateien werden ersetzt. Dadurch kann der Schritt
    nach einem Fehler mit denselben Eingaben wiederholt werden.
    """

    information_files = sorted(Path(artifact_root).glob("_INFO_*.json"))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

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

    # Release-Beschreibung mit Kurzüberblick und Download-Links zu den Informationen.
    download_root = (
        f"{server_url.rstrip('/')}/{repository}/releases/download/"
        f"{urllib.parse.quote(release_tag, safe='')}"
    )
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
        link = f"{download_root}/{urllib.parse.quote(name, safe='')}"
        lines.append(f"- [Herunterladen]({link}): `{name}`")
    body = "\n".join(lines) + "\n"

    repository_path = urllib.parse.quote(repository)
    release_path = urllib.parse.quote(release_tag, safe="")
    releases_url = f"{api_url.rstrip('/')}/repos/{repository_path}/releases"

    # Vorhandenes Release laden oder bei der ersten Veröffentlichung anlegen.
    release = github_api.request(
        method="GET",
        url=f"{releases_url}/tags/{release_path}",
        token=token,
        failure=Status.GITHUB_RELEASE_FAILED,
        missing_ok=True,
    )
    release_values = {
        "tag_name": release_tag,
        "name": f"Release {release_tag}",
        "body": body,
        "draft": False,
        "prerelease": False,
    }
    existing_assets: list[dict[str, Any]] = []
    if release is None:
        release = github_api.request(
            method="POST",
            url=releases_url,
            token=token,
            failure=Status.GITHUB_RELEASE_FAILED,
            payload=release_values,
        )
    else:
        match release:
            case {"id": int(release_id), "assets": list(existing_assets)}:
                pass
            case _:
                raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Vorhandenes GitHub Release ist ungültig")
        release = github_api.request(
            method="PATCH",
            url=f"{releases_url}/{release_id}",
            token=token,
            failure=Status.GITHUB_RELEASE_FAILED,
            payload=release_values,
        )

    # Upload-URL und öffentliche Release-Adresse aus der API-Antwort übernehmen.
    match release:
        case {"upload_url": str(upload_url), "html_url": str(release_url)}:
            upload_url = upload_url.split("{", 1)[0]
        case _:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub Release ist unvollständig")

    # Gleichnamige Informationsdateien aus einem früheren Lauf vor dem erneuten Upload entfernen.
    assets_by_name: dict[str, int] = {}
    for asset in existing_assets:
        match asset:
            case {"name": str(name), "id": int(asset_id)}:
                assets_by_name[name] = asset_id
            case _:
                raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub-Asset ist ungültig")
    for information in information_files:
        name = information.name
        asset_id = assets_by_name.get(name)
        if asset_id is not None:
            github_api.request(
                method="DELETE",
                url=f"{releases_url}/assets/{asset_id}",
                token=token,
                failure=Status.GITHUB_RELEASE_FAILED,
            )
        github_api.request(
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
