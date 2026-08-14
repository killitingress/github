"""Veröffentlicht die Rückmeldung zu einer Mainframe-Lieferung in GitHub.

Nach der erfolgreichen FTP-/JES-Übergabe entsteht im Mandanten-Repository ein
GitHub Release. Seine Beschreibung fasst die Lieferung zusammen. Die beim
Paketbau erzeugten Informationsdateien werden als Downloads angehängt.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .process import DeliveryError, NETWORK_TIMEOUT, Status
from .release import FULL_SUFFIX


# API-Version für das Anlegen von Releases und das Hochladen ihrer Dateien.
GITHUB_API_VERSION = "2022-11-28"
# GitHub empfiehlt diesen Medientyp für JSON-Antworten der REST-API.
GITHUB_JSON_MEDIA_TYPE = "application/vnd.github+json"


def _github_request(
    *,
    method: str,
    url: str,
    token: str,
    payload: dict[str, object] | None = None,
    content: bytes | None = None,
    content_type: str | None = None,
    missing_ok: bool = False,
) -> Any:
    """Sendet eine Anfrage an die GitHub-API und liest ihre JSON-Antwort.

    Die Funktion versendet JSON-Daten und Dateien. Wenn `missing_ok` gesetzt ist,
    gibt sie bei HTTP 404 `None` zurück. Andere HTTP- und Verbindungsfehler
    beenden die Veröffentlichung. Das Token wird im Authorization-Header
    übertragen.
    """

    body = json.dumps(payload).encode("utf-8") if payload is not None else content
    headers = {
        "Accept": GITHUB_JSON_MEDIA_TYPE,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    elif content_type is not None:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        # Fehlende Releases dürfen bei der ersten Anlage ohne Fehler fehlen.
        if missing_ok and exc.code == 404:
            return None
        # GitHub liefert Fehlerdetails als JSON mit einem `message`-Feld.
        detail = ""
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            pass
        else:
            match error_body:
                case {"message": str(message)}:
                    detail = message
                case _:
                    pass
        suffix = f": {detail}" if detail else ""
        raise DeliveryError(
            Status.GITHUB_RELEASE_FAILED,
            f"GitHub antwortet mit HTTP {exc.code}{suffix}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub ist nicht erreichbar") from exc

    # DELETE und manche erfolgreiche Uploads antworten ohne JSON-Körper.
    if not response_body:
        return None
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub-Antwort ist ungültig") from exc


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

    information_files = sorted(Path(artifact_root).glob("_INFO_*.txt"))
    if not information_files:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Informationsdateien fehlen")

    # Release-Beschreibung mit Kurzüberblick und Download-Links zu den Lieferbelegen.
    download_root = (
        f"{server_url.rstrip('/')}/{repository}/releases/download/"
        f"{urllib.parse.quote(release_tag, safe='')}"
    )
    lines = [
        "## Lieferung",
        "",
        f"- Release: `{release_tag}`",
        f"- Lieferart: `{'FULL' if release_tag.endswith(FULL_SUFFIX) else 'DELTA'}`",
        f"- Commit: `{source_sha}`",
        "",
        "Die Pakete und die zugehörige JCL wurden von FTP und JES angenommen.",
        "",
        "## Informationsdateien",
        "",
    ]
    for information in information_files:
        name = information.name
        link = f"{download_root}/{urllib.parse.quote(name, safe='')}"
        lines.append(f"- [Herunterladen]({link}): `{name}`")
    body = "\n".join(lines) + "\n"

    repository_path = urllib.parse.quote(repository, safe="/")
    release_path = urllib.parse.quote(release_tag, safe="")
    releases_url = f"{api_url.rstrip('/')}/repos/{repository_path}/releases"

    # Vorhandenes Release laden oder bei der ersten Veröffentlichung anlegen.
    release = _github_request(
        method="GET",
        url=f"{releases_url}/tags/{release_path}",
        token=token,
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
        release = _github_request(method="POST", url=releases_url, token=token, payload=release_values)
    else:
        match release:
            case {"id": int(release_id), "assets": list(existing_assets)}:
                pass
            case _:
                raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Vorhandenes GitHub Release ist ungültig")
        release = _github_request(
            method="PATCH",
            url=f"{releases_url}/{release_id}",
            token=token,
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
            _github_request(
                method="DELETE",
                url=f"{releases_url}/assets/{asset_id}",
                token=token,
            )
        _github_request(
            method="POST",
            url=f"{upload_url}?{urllib.parse.urlencode({'name': name})}",
            token=token,
            content=information.read_bytes(),
            content_type="text/plain; charset=utf-8",
        )

    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED.value,
        "repository": repository,
        "release_tag": release_tag,
        "release_url": release_url,
    }
