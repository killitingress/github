"""Bereitet eine Lieferung vor, bestätigt sie und erzeugt den Liefer-Tag.

Die Vorprüfung hält Branchstand und SHA fest. Die Ausführung taggt diesen
festgehaltenen Stand.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
from pathlib import Path

from . import config, git, github
from .config import Configuration, release_branches
from .process import DeliveryError, Status
from .project_package import _FULL_RELEASE, project_elements, release_scope


# Datei im Artefakt mit Tag, SHA, Branch, Repository und vorbereitender Person.
_VORBEREITUNG_DATEI = "vorbereitung.json"


def _require_lieferung_source(
    configuration: Configuration,
    root: Path,
    tag: str,
    branch: str,
    sha: str,
    *,
    require_current_tip: bool,
) -> tuple[str, str]:
    """Prüft Liefer-Tag, Branch und die festgehaltene SHA.

    Die Aktualität der Branchspitze gilt für die Vorbereitung. Die spätere
    Ausführung taggt die festgehaltene SHA, auch wenn der Branch weitergewandert
    ist.
    """

    # Liefer-Tag und Releaselinie prüfen.
    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Liefer-Tag")
    releaselinie = tag_match.group("releaselinie")
    release = tag_match.group("release")

    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")

    # Checkout muss zur festgehaltenen SHA passen und der Tag darf noch fehlen.
    if git.resolve(root, "HEAD") != sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zur festgehaltenen SHA")

    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist bereits vorhanden")

    # Bereitstellungsbranch oder Releaselinie-Branch zuordnen.
    bereitstellung = git.BEREITSTELLUNG_BRANCH_RE.fullmatch(branch)
    if bereitstellung is not None:
        if release == _FULL_RELEASE:
            raise DeliveryError(Status.VALIDATION_FAILED, ".100 entsteht auf main oder release/nnn")

        if (bereitstellung.group(1), bereitstellung.group(2)) != (releaselinie, release):
            raise DeliveryError(Status.SOURCE_FAILED, "Bereitstellungsbranch passt nicht zum Liefer-Tag")
    elif branch not in release_branches(configuration, releaselinie):
        raise DeliveryError(Status.SOURCE_FAILED, "Branch passt nicht zur Releaselinie")

    # Bei der Vorbereitung muss der Branch aktuell sein.
    if require_current_tip and git.resolve(root, f"refs/remotes/origin/{branch}") != sha:
        raise DeliveryError(Status.SOURCE_FAILED, "ausgewählter Branchstand ist nicht mehr aktuell")
    return releaselinie, release


def _summary(
    configuration: Configuration,
    root: Path,
    tag: str,
    branch: str,
    sha: str,
    releaselinie: str,
    release: str,
) -> str:
    """Erzeugt die Markdown-Vorprüfung für die festgehaltene SHA."""

    base, changes = release_scope(root, tag, sha)
    delivery_type = "FULL" if base is None else "DELTA"
    base_reference = "–" if base is None else base[0]
    lines = [
        "## Liefer-Vorprüfung",
        "",
        "| Angabe | Wert |",
        "|---|---|",
        f"| Lieferung | `{tag}` |",
        f"| Branch | `{branch}` |",
        f"| Commit | `{sha}` |",
        f"| Lieferart | `{delivery_type}` |",
        f"| Bezugsstand | `{base_reference}` |",
    ]

    if run_id := os.environ.get("GITHUB_RUN_ID"):
        lines.append(f"| Vorbereitungs-ID | `{run_id}` |")
    lines.extend(("", ""))

    # Projektbezogene Elementlisten für Lieferumfang und optionalen Vorgänger.
    sections: list[tuple[str, tuple[str, str] | None, list[git.GitChange]]] = [
        ("Lieferumfang", base, changes),
    ]
    if release != _FULL_RELEASE:
        listed = git.run(root, "tag", "--list", f"r{releaselinie}.*").decode().splitlines()
        earlier = []
        for name in listed:
            tag_match = git.RELEASE_TAG_RE.fullmatch(name)
            if tag_match is not None and tag_match.group("release") < release:
                earlier.append(tag_match.group("release"))

        if earlier:
            previous = f"r{releaselinie}.{max(earlier)}"
            if base is None or previous != base[0]:
                previous_sha = git.resolve(root, f"refs/tags/{previous}")
                sections.append(
                    (f"Änderungen seit `{previous}`", (previous, previous_sha), git.changes(root, previous_sha, sha))
                )

    for heading, section_base, section_changes in sections:
        lines.extend((f"## {heading}", ""))
        for project in configuration.projects:
            elements = project_elements(root, project, base=section_base, changes=section_changes)
            lines.extend((f"### `{project}`", ""))

            if elements:
                lines.extend(f"- `{status}` `{path}`" for status, path in elements)
            else:
                lines.append("- Keine Änderungen")
            lines.append("")
        lines.extend((f"Zielstand: `{sha}`", ""))

    return "\n".join(lines)


def run_command(arguments: argparse.Namespace) -> dict[str, object]:
    """Bereitet den Lieferstand vor, bestätigt ihn oder erzeugt den Liefer-Tag."""

    # SHA festhalten und Lieferumfang anzeigen.
    if arguments.lieferung_command == "check":
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", "."))
        source = workspace / "source"
        configuration = config.load_configuration(source, os.environ["SOURCE_REPOSITORY"])
        releaselinie, release = _require_lieferung_source(
            configuration,
            source,
            arguments.tag,
            arguments.branch,
            arguments.source_sha,
            require_current_tip=True,
        )
        vorbereitung = workspace / _VORBEREITUNG_DATEI
        vorbereitung.write_text(
            json.dumps(
                {
                    "tag": arguments.tag,
                    "sha": arguments.source_sha,
                    "branch": arguments.branch,
                    "repository": os.environ["SOURCE_REPOSITORY"],
                    "actor": arguments.actor,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "status": Status.LIEFERUNG_CHECKED.value,
            "summary": _summary(
                configuration,
                source,
                arguments.tag,
                arguments.branch,
                arguments.source_sha,
                releaselinie,
                release,
            ),
            "outputs": {
                "vorbereitung_path": vorbereitung.as_posix(),
                "lieferung_tag": arguments.tag,
                "source_sha": arguments.source_sha,
                "source_branch": arguments.branch,
                "prepare_actor": arguments.actor,
            },
        }

    # Heruntergeladene Vorbereitung durch dieselbe oder eine zweite Person bestätigen.
    if arguments.lieferung_command == "ausfuehren":
        try:
            payload = json.loads(arguments.vorbereitung.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig") from exc
        match payload:
            case {
                "tag": str(tag),
                "sha": str(sha),
                "branch": str(branch),
                "repository": str(repository),
                "actor": str(prepare_actor),
            }:
                pass
            case _:
                raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig")

        if repository != os.environ["SOURCE_REPOSITORY"]:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört zu einem anderen Repository")

        if not prepare_actor or not arguments.actor:
            raise DeliveryError(Status.SOURCE_FAILED, "Lieferperson fehlt")
        lieferweg = "Direktlieferung" if prepare_actor == arguments.actor else "Vier-Augen-Freigabe"
        return {
            "status": Status.LIEFERUNG_BESTAETIGT.value,
            "summary": "\n".join(
                (
                    "## Lieferung bestätigt",
                    "",
                    f"- Liefer-Tag: `{tag}`",
                    f"- Commit: `{sha}`",
                    f"- Lieferweg: {lieferweg}",
                    "",
                )
            ),
            "outputs": {
                "lieferung_tag": tag,
                "source_sha": sha,
                "source_branch": branch,
                "prepare_actor": prepare_actor,
            },
        }

    # Liefer-Tag auf der festgehaltenen SHA erzeugen.
    if arguments.lieferung_command == "tag":
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", "."))
        source = workspace / "source"
        configuration = config.load_configuration(source, os.environ["SOURCE_REPOSITORY"])
        _require_lieferung_source(
            configuration,
            source,
            arguments.tag,
            arguments.branch,
            arguments.source_sha,
            require_current_tip=False,
        )

        if not arguments.prepare_actor or not arguments.execute_actor:
            raise DeliveryError(Status.SOURCE_FAILED, "Lieferperson fehlt")
        repository = os.environ["SOURCE_REPOSITORY"]
        github.request(
            method="POST",
            url=f"{arguments.api_url.rstrip('/')}/repos/{urllib.parse.quote(repository, safe='/')}/git/refs",
            token=os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
            failure=Status.SOURCE_FAILED,
            payload={"ref": f"refs/tags/{arguments.tag}", "sha": arguments.source_sha},
        )
        return {
            "status": Status.LIEFERUNG_TAGGED.value,
            "outputs": {"lieferung_tag": arguments.tag, "source_sha": arguments.source_sha},
        }

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
