"""Bereitet eine Lieferung vor, bestätigt sie und erzeugt den Liefer-Tag.

Die Vorprüfung hält Branchstand und SHA fest. Für eine neue Lieferung wird die
Vorbereitung ermittelt und bestätigt. Bei einer Wiederholung bestimmt der
vorhandene Liefer-Tag den Stand.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse

from . import git, github
from .config import (
    WORKFLOW_VORBEREITUNG_DATEI,
    Configuration,
    mandant_source,
    workflow_workspace,
)
from .process import DeliveryError, Status
from .project_package import _FULL_RELEASE, project_elements, release_scope


# Das Artefakt das während der Vorbereitung erzeugt wird
_VORBEREITUNG_ARTEFAKT = "{tag}-lieferungsartefakt"


def _vorbereitungslauf(api_url: str, repository: str, tag: str, token: str) -> int | None:
    """Ermittelt den neuesten noch verfügbaren Vorbereitungslauf.

    Sucht in GitHub Actions nach dem Lieferungsartefakt zum Liefer-Tag.
    """

    repository_path = urllib.parse.quote(repository, safe="/")
    artifact_name = _VORBEREITUNG_ARTEFAKT.format(tag=tag)
    query = urllib.parse.urlencode({"name": artifact_name, "per_page": 100})
    document = github.request(
        method="GET",
        url=f"{api_url.rstrip('/')}/repos/{repository_path}/actions/artifacts?{query}",
        token=token,
        failure=Status.SOURCE_FAILED,
    )
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakte können nicht ermittelt werden")

    available = [
        artifact for artifact in document["artifacts"]
        if isinstance(artifact, dict) and artifact.get("expired") is False
    ]
    if not available:
        return None

    try:
        newest = max(available, key=lambda artifact: (artifact["created_at"], artifact["id"]))
        return newest["workflow_run"]["id"]
    except (KeyError, TypeError):
        raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig") from None


def _pruefe_lieferquelle(configuration: Configuration, root: Path, tag: str, branch: str, sha: str) -> tuple[str, str]:
    """Prüft Liefer-Tag, Branch und ob der ausgewählte Branchstand noch aktuell ist."""

    # Liefer-Tag und Releaselinie prüfen.
    tag_match = git.LIEFER_TAG_RE.fullmatch(tag)
    if tag_match is None:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"ungültiges Format des Liefer-Tags - braucht rnnn.nnn, bekommen {tag}",
        )
    releaselinie = tag_match.group("releaselinie")
    zwischenrelease = tag_match.group("zwischenrelease")

    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Liefer-Tag ist bereits vorhanden")

    # Bereitstellungsbranch oder Releaselinie-Branch zuordnen.
    bereitstellung = git.BEREITSTELLUNG_BRANCH_RE.fullmatch(branch)
    if bereitstellung is not None:
        if zwischenrelease == _FULL_RELEASE:
            raise DeliveryError(Status.VALIDATION_FAILED, ".100 entsteht nur auf main oder release/nnn")

        if bereitstellung.groups() != (releaselinie, zwischenrelease):
            raise DeliveryError(Status.SOURCE_FAILED, "Bereitstellungsbranch passt nicht zum Liefer-Tag")
    elif branch not in configuration.release_branches(releaselinie):
        raise DeliveryError(Status.SOURCE_FAILED, "Branch passt nicht zur Releaselinie")

    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, f"Releaselinie {releaselinie} ist ungültig")

    if git.resolve(root, f"refs/remotes/origin/{branch}") != sha:
        raise DeliveryError(Status.SOURCE_FAILED, "ausgewählter Branchstand ist nicht mehr aktuell")
    return releaselinie, zwischenrelease


def _summary(
    configuration: Configuration,
    root: Path,
    tag: str,
    branch: str,
    sha: str,
    releaselinie: str,
    zwischenrelease: str,
) -> str:
    """Erzeugt das Markdown der Vorprüfung"""

    base, changes = release_scope(root, sha, releaselinie=releaselinie, zwischenrelease=zwischenrelease)
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

    lines.append("")

    # Projektbezogene Elementlisten für Lieferumfang und optionalen Vorgänger.
    sections: list[tuple[str, tuple[str, str] | None, list[git.GitChange]]] = [
        ("Lieferumfang", base, changes),
    ]
    if zwischenrelease != _FULL_RELEASE:
        listed = git.execute(root, "tag", "--list", f"r{releaselinie}.*").decode().splitlines()
        earlier = []
        for name in listed:
            tag_match = git.LIEFER_TAG_RE.fullmatch(name)
            if tag_match is not None and tag_match.group("zwischenrelease") < zwischenrelease:
                earlier.append(tag_match.group("zwischenrelease"))

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


def run(arguments: argparse.Namespace) -> dict[str, object]:
    """Bereitet den Lieferstand vor, ermittelt ihn, bestätigt ihn oder erzeugt den Liefer-Tag."""

    # Resolve => Vorbereitung anhand des Liefer-Tags ermitteln
    if arguments.delivery_command == "resolve":
        if git.LIEFER_TAG_RE.fullmatch(arguments.tag) is None:
            raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Liefer-Tag")

        api_url = os.environ["GITHUB_API_URL"]
        repository = os.environ["GITHUB_REPOSITORY"]
        token = os.environ["GITHUB_TOKEN"]
        repository_path = urllib.parse.quote(repository, safe="/")
        tag_path = urllib.parse.quote(arguments.tag, safe="")

        # Liefer-Tag aus GitHub abfragen
        reference = github.request(
            method="GET",
            url=f"{api_url.rstrip('/')}/repos/{repository_path}/git/ref/tags/{tag_path}",
            token=token,
            failure=Status.SOURCE_FAILED,
            missing_ok=True,
        )

        # wenn der Liefer-Tag existiert, wird seine SHA zurückgegeben
        if reference is not None:
            return {"outputs": {"wiederholung": "true", "source_sha": reference["object"]["sha"]}}

        # Liefer-Tag existiert nicht =>Vorbereitung ermitteln
        run_id = _vorbereitungslauf(api_url, repository, arguments.tag, token)
        if run_id is None:
            raise DeliveryError(Status.SOURCE_FAILED, "Für den Liefer-Tag besteht keine Vorbereitung")

        # Lauf-ID und Artefakt-Name der existierenden Vorbereitung zurückgeben
        name = _VORBEREITUNG_ARTEFAKT.format(tag=arguments.tag)
        return {"outputs": {"wiederholung": "false", "vorbereitung_id": run_id, "vorbereitung_name": name}}

    # Check => HA festhalten und Lieferumfang anzeigen
    if arguments.delivery_command == "check":
        source = mandant_source()
        repository = os.environ["GITHUB_REPOSITORY"]
        branch = os.environ["GITHUB_REF_NAME"]
        sha = git.resolve(source, "HEAD")
        actor = os.environ["GITHUB_ACTOR"]
        configuration = Configuration.load(source, repository)
        releaselinie, zwischenrelease = _pruefe_lieferquelle(configuration, source, arguments.tag, branch, sha)

        # Vorbereitung speichern
        vorbereitung = workflow_workspace() / WORKFLOW_VORBEREITUNG_DATEI
        vorbereitung.write_text(
            json.dumps(
                {
                    "tag": arguments.tag,
                    "sha": sha,
                    "branch": branch,
                    "repository": repository,
                    "prepare_actor": actor,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        # Vorbereitung inkl. Summary zurückgeben
        return {
            "status": Status.LIEFERUNG_CHECKED.value,
            "summary": _summary(configuration, source, arguments.tag, branch, sha, releaselinie, zwischenrelease),
            "outputs": {
                "vorbereitung_path": vorbereitung.as_posix(),
                "vorbereitung_name": _VORBEREITUNG_ARTEFAKT.format(tag=arguments.tag),
            },
        }

    # Config => Vorbereitung (durch dieselbe oder eine zweite Person) bestätigen
    if arguments.delivery_command == "confirm":
        # Vorbereitung laden
        vorbereitung = workflow_workspace() / "vorbereitung" / WORKFLOW_VORBEREITUNG_DATEI
        try:
            payload = json.loads(vorbereitung.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig") from exc
        match payload:
            case {
                "tag": str(tag),
                "sha": str(sha),
                "branch": str(branch),
                "repository": str(repository),
                "prepare_actor": str(prepare_actor),
            }:
                pass
            case _:
                raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitungsartefakt ist ungültig")

        # Vorbereitung prüfen
        if repository != os.environ["GITHUB_REPOSITORY"]:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört zu einem anderen Repository")
        if tag != arguments.tag:
            raise DeliveryError(Status.SOURCE_FAILED, "Vorbereitung gehört zu einem anderen Liefer-Tag")
        direktlieferung = prepare_actor == os.environ["GITHUB_ACTOR"]
        if direktlieferung and not arguments.confirm_direct_delivery:
            raise DeliveryError(
                Status.VALIDATION_FAILED,
                "Direktlieferung muss mit der Abweichung vom empfohlenen 4-Augenfall und dem damit "
                "verbundenen Risiko bewusst bestätigt werden",
            )

        # Lieferung bestätigen => Status setzen und Summary zurückgeben
        return {
            "status": Status.LIEFERUNG_BESTAETIGT.value,
            "summary": "\n".join(
                (
                    "## Lieferung bestätigt",
                    "",
                    f"- Liefer-Tag: `{tag}`",
                    f"- Commit: `{sha}`",
                    f"- Lieferweg: {'Direktlieferung' if direktlieferung else '4-Augenfall'}",
                    "",
                )
            ),
            "outputs": {
                "source_sha": sha,
            },
        }

    # Tag => Liefer-Tag auf der in der Vorbereitung festgehaltenen SHA im Mandanten-Repository erzeugen
    if arguments.delivery_command == "tag":
        repository = os.environ["GITHUB_REPOSITORY"]
        source_sha = git.resolve(mandant_source(), "HEAD")
        github.request(
            method="POST",
            url=f"{os.environ['GITHUB_API_URL'].rstrip('/')}/repos/{urllib.parse.quote(repository, safe='/')}/git/refs",
            token=os.environ["GITHUB_TOKEN"],
            failure=Status.SOURCE_FAILED,
            payload={"ref": f"refs/tags/{arguments.tag}", "sha": source_sha},
        )
        return {"status": Status.LIEFERUNG_TAGGED.value}

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Lieferbefehl")
