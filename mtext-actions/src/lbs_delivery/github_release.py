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

from .manifest import load_and_verify
from .process import DeliveryError, Status


# Diese Version bezeichnet den von GitHub Enterprise Server dokumentierten
# REST-Vertrag für Releases und Release-Assets.
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
    """Führt einen GitHub-REST-Aufruf aus und übersetzt Transportfehler.

    JSON-Aufrufe und binäre Asset-Uploads verwenden dieselbe abgesicherte
    HTTP-Grenze. Das Zugangstoken erscheint weder in URLs noch in Fehlertexten.
    """

    if payload is not None and content is not None:
        raise ValueError("payload und content dürfen nicht gemeinsam gesetzt sein")

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
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            detail = error_body.get("message", "") if isinstance(error_body, dict) else ""
        except (UnicodeError, json.JSONDecodeError):
            detail = ""
        suffix = f": {detail}" if detail else ""
        raise DeliveryError(
            Status.GITHUB_RELEASE_FAILED,
            f"GitHub antwortet mit HTTP {exc.code}{suffix}",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub ist nicht erreichbar") from exc

    if not response_body:
        return None
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub-Antwort ist ungültig") from exc


def _markdown_cell(value: object) -> str:
    """Schützt einen Wert vor einer unbeabsichtigten Trennung der Markdown-Tabelle."""

    return str(value).replace("|", "\\|").replace("\n", " ")


def _release_body(
    manifest: dict[str, Any], information_files: list[dict[str, Any]], *, server_url: str,
) -> str:
    """Erzeugt die lesbare GitHub-Beschreibung aus dem geprüften Manifest."""

    repository = manifest["repository"]
    release_tag = manifest["release_tag"]
    previous_tag = manifest.get("previous_tag")
    comparison = f"seit {previous_tag}" if previous_tag else "im Release"
    download_root = (
        f"{server_url.rstrip('/')}/{repository}/releases/download/"
        f"{urllib.parse.quote(release_tag, safe='')}"
    )

    lines = [
        "## Lieferung",
        "",
        f"- Mandant: `{manifest['mandant']}`",
        f"- Release: `{release_tag}`",
        f"- Lieferart: `{manifest['delivery_type']}`",
        f"- Commit: `{manifest['target_sha']}`",
        "",
        "Die Pakete und die zugehörige JCL wurden von FTP und JES angenommen.",
        "",
        "## Projekte",
        "",
        f"| Projekt | Änderungen {comparison} | Einträge im Paket | Informationsdatei |",
        "|---|---:|---:|---|",
    ]
    for information in information_files:
        name = information["path"]
        link = f"{download_root}/{urllib.parse.quote(name, safe='')}"
        lines.append(
            f"| {_markdown_cell(information['project'])} "
            f"| {len(information['changes'])} "
            f"| {len(information['archive_entries'])} "
            f"| [{_markdown_cell(name)}]({link}) |"
        )
    return "\n".join(lines) + "\n"


def publish_github_release(
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    api_url: str,
    server_url: str,
    repository: str,
    release_tag: str,
    token: str,
) -> dict[str, object]:
    """Legt das GitHub Release an und hängt die Informationsdateien an.

    Ein bereits vorhandenes Release wird aktualisiert. Gleichnamige, von diesem
    Ablauf erzeugte Informationsdateien werden ersetzt. Dadurch kann der Schritt
    nach einem Fehler mit denselben Eingaben wiederholt werden.
    """

    manifest, _packages = load_and_verify(manifest_path, artifact_root)
    try:
        if manifest["repository"] != repository or manifest["release_tag"] != release_tag:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub-Ziel passt nicht zum Manifest")
        if not all(
            isinstance(manifest[name], str)
            for name in ("repository", "mandant", "release_tag", "delivery_type", "target_sha")
        ):
            raise TypeError
        information_files = [
            artifact for artifact in manifest["artifacts"]
            if artifact.get("kind") == "information"
        ]
        if not information_files:
            raise TypeError
        for information in information_files:
            if (
                not isinstance(information.get("path"), str)
                or not isinstance(information.get("project"), str)
                or not isinstance(information.get("changes"), list)
                or not isinstance(information.get("archive_entries"), list)
            ):
                raise TypeError
    except (KeyError, TypeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Manifest ist für das GitHub Release unvollständig") from exc

    repository_path = urllib.parse.quote(repository, safe="/")
    release_path = urllib.parse.quote(release_tag, safe="")
    releases_url = f"{api_url.rstrip('/')}/repos/{repository_path}/releases"
    release = _github_request(
        method="GET",
        url=f"{releases_url}/tags/{release_path}",
        token=token,
        missing_ok=True,
    )
    body = _release_body(manifest, information_files, server_url=server_url)
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
        try:
            release_id = release["id"]
            assets = release.get("assets", [])
            if not isinstance(release_id, int) or not isinstance(assets, list):
                raise TypeError
            existing_assets = assets
        except (KeyError, TypeError) as exc:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "Vorhandenes GitHub Release ist ungültig") from exc
        release = _github_request(
            method="PATCH",
            url=f"{releases_url}/{release_id}",
            token=token,
            payload=release_values,
        )

    try:
        upload_url = release["upload_url"].split("{", 1)[0]
        release_url = release["html_url"]
        if not isinstance(upload_url, str) or not isinstance(release_url, str):
            raise TypeError
    except (KeyError, TypeError, AttributeError) as exc:
        raise DeliveryError(Status.GITHUB_RELEASE_FAILED, "GitHub Release ist unvollständig") from exc

    assets_by_name = {
        asset.get("name"): asset.get("id")
        for asset in existing_assets
        if isinstance(asset, dict) and isinstance(asset.get("name"), str) and isinstance(asset.get("id"), int)
    }
    for information in information_files:
        name = information["path"]
        asset_id = assets_by_name.get(name)
        if asset_id is not None:
            _github_request(
                method="DELETE",
                url=f"{releases_url}/assets/{asset_id}",
                token=token,
            )
        try:
            content = (Path(artifact_root) / name).read_bytes()
        except OSError as exc:
            raise DeliveryError(Status.GITHUB_RELEASE_FAILED, f"Informationsdatei fehlt: {name}") from exc
        _github_request(
            method="POST",
            url=f"{upload_url}?{urllib.parse.urlencode({'name': name})}",
            token=token,
            content=content,
            content_type="text/plain; charset=utf-8",
        )

    return {
        "status": Status.GITHUB_RELEASE_PUBLISHED.value,
        "repository": repository,
        "release_tag": release_tag,
        "release_url": release_url,
    }
