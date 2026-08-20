"""Bereitet den Release-Freigabe-PR vor, prüft ihn und schließt ihn ab.

Der technische Freigabe-Branch aktualisiert `letztes_release` in der
Mandantenkonfiguration. Der Antragsteller eröffnet den Pull Request selbst und
ist damit dessen Autor. Ein GitHub-Check zeigt den geplanten Lieferumfang. Nach
Review und Merge wird der Merge-Commit mit der freigegebenen Version getaggt.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import config, git, github
from .config import Configuration, MANDANT_CONFIG_PATH, release_branches
from .process import DeliveryError, Status
from .project_package import project_elements, release_scope


# Technische Freigabe-Branches tragen Release-Version und Laufbezug. Der
# Abschluss erkennt damit den vorgesehenen Pull-Request-Ablauf.
APPROVAL_BRANCH_PREFIX = "release-approval/"


def _regular_release_tag(tag: str, failure: Status, message: str) -> str:
    """Liest die Releaselinie eines Release-Tags ohne Buchstabensuffix."""

    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None or tag_match.group("beta_suffix"):
        raise DeliveryError(failure, message)
    return f"R{tag_match.group('releaselinie')}"


def _require_release_branch(
    configuration: Configuration, branch: str, releaselinie: str, failure: Status, message: str
) -> None:
    """Prüft die technische Zuordnung von Lieferbranch und Releaselinie."""

    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(failure, "Releaselinie ist unbekannt")
    if branch not in release_branches(configuration, releaselinie):
        raise DeliveryError(failure, message)


def _validated_release_tag(
    configuration: Configuration,
    root: Path,
    approval_branch: str,
    branch: str,
) -> str:
    """Prüft die gemeinsame Tag-, Branch- und Konfigurationsangabe des PRs."""

    if not approval_branch.startswith(APPROVAL_BRANCH_PREFIX):
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist keine Release-Freigabe")
    tag = approval_branch.removeprefix(APPROVAL_BRANCH_PREFIX).split("/", 1)[0]
    releaselinie = _regular_release_tag(
        tag,
        Status.SOURCE_FAILED,
        "Freigabe-Branch enthält keinen Release-Tag ohne Buchstabensuffix",
    )
    _require_release_branch(
        configuration,
        branch,
        releaselinie,
        Status.SOURCE_FAILED,
        "Zielbranch passt nicht zur Release-Version",
    )
    if configuration.letztes_release != tag:
        raise DeliveryError(Status.SOURCE_FAILED, "Mandantenkonfiguration nennt eine andere Release-Version")
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag ist bereits vorhanden")
    return tag


def prepare_release_approval(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    tag: str,
    branch: str,
    source_sha: str,
    run_reference: str,
) -> tuple[str, Path]:
    """Aktualisiert die Release-Version und benennt den Freigabe-Branch."""

    root = Path(repository_root)
    releaselinie = _regular_release_tag(
        tag,
        Status.VALIDATION_FAILED,
        "Freigabe-PR benötigt einen Release-Tag ohne Buchstabensuffix",
    )
    _require_release_branch(
        configuration,
        branch,
        releaselinie,
        Status.SOURCE_FAILED,
        "Branch passt nicht zur Release-Version",
    )
    if git.resolve(root, "HEAD") != source_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum ausgewählten Branchstand")
    if git.resolve(root, f"refs/remotes/origin/{branch}") != source_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "ausgewählter Branchstand ist nicht mehr aktuell")
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag ist bereits vorhanden")

    path = root / MANDANT_CONFIG_PATH
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        document["mandant"]["letztes_release"] = tag
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "Mandantenkonfiguration kann nicht aktualisiert werden") from exc

    return f"{APPROVAL_BRANCH_PREFIX}{tag}/{run_reference}", path


def check_release_approval(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    approval_branch: str,
    branch: str,
    target_sha: str,
) -> str:
    """Prüft den geplanten Release und erstellt seine Markdown-Zusammenfassung."""

    root = Path(repository_root)
    if git.resolve(root, "HEAD") != target_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Pull Request")
    tag = _validated_release_tag(configuration, root, approval_branch, branch)

    base, changes = release_scope(root, tag, target_sha)
    delivery_type = "FULL" if base is None else "DELTA"
    base_reference = "–" if base is None else base[0]
    lines = [
        "## Release-Vorprüfung",
        "",
        "| Angabe | Wert |",
        "|---|---|",
        f"| Release | `{tag}` |",
        f"| Lieferbranch | `{branch}` |",
        f"| Commit | `{target_sha}` |",
        f"| Lieferart | `{delivery_type}` |",
        f"| Bezugsstand | `{base_reference}` |",
        "",
        "## Lieferumfang",
        "",
    ]
    for project in configuration.projects:
        elements = project_elements(root, project, base=base, changes=changes)
        lines.extend((f"### `{project}`", "", f"Zielstand: `{target_sha}`", ""))
        if elements:
            lines.extend(f"- `{status}` `{path}`" for status, path in elements)
        else:
            lines.append("- Keine Änderungen")
        lines.append("")
    return "\n".join(lines)


def finalize_release_approval(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    approval_branch: str,
    branch: str,
    merge_sha: str,
    pull_request: dict[str, object],
) -> str:
    """Prüft den zusammengeführten Freigabe-PR und gibt den Release-Tag zurück."""

    root = Path(repository_root)
    match pull_request:
        case {
            "merged": True,
            "merge_commit_sha": str(pull_request_merge_sha),
            "base": {"ref": str(pull_request_branch)},
            "head": {"ref": str(pull_request_approval_branch)},
        }:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist nicht zusammengeführt")
    if pull_request_merge_sha != merge_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request nennt einen anderen Merge-Commit")
    if pull_request_branch != branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request wurde in einen anderen Branch zusammengeführt")
    if pull_request_approval_branch != approval_branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request gehört zu einem anderen Freigabe-Branch")
    if git.resolve(root, "HEAD") != merge_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Freigabe-Merge")

    return _validated_release_tag(configuration, root, approval_branch, branch)


def run_command(arguments: argparse.Namespace) -> dict[str, object]:
    """Bereitet die Release-Freigabe vor, prüft sie oder schließt sie ab."""

    source = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "source"
    repository = os.environ["SOURCE_REPOSITORY"]
    configuration = config.load_configuration(source, repository)
    if arguments.approval_command == "prepare":
        approval_branch, path = prepare_release_approval(
            configuration,
            repository_root=source,
            tag=arguments.tag,
            branch=arguments.branch,
            source_sha=arguments.source_sha,
            run_reference=arguments.run_reference,
        )
        return {
            "status": Status.RELEASE_APPROVAL_READY.value,
            "outputs": {
                "approval_branch": approval_branch,
                "approval_path": path.relative_to(source).as_posix(),
            },
        }

    if arguments.approval_command == "check":
        summary = check_release_approval(
            configuration,
            repository_root=source,
            approval_branch=arguments.approval_branch,
            branch=arguments.branch,
            target_sha=arguments.target_sha,
        )
        return {
            "status": Status.RELEASE_APPROVAL_CHECKED.value,
            "summary": summary,
        }

    if arguments.approval_command == "finalize":
        tag = finalize_release_approval(
            configuration,
            repository_root=source,
            approval_branch=arguments.approval_branch,
            branch=arguments.branch,
            merge_sha=arguments.merge_sha,
            pull_request=github.read_pull_request(
                api_url=arguments.api_url,
                repository=repository,
                number=arguments.pull_request_number,
                token=os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
            ),
        )
        return {"status": Status.RELEASE_APPROVAL_VALIDATED.value, "outputs": {"release_tag": tag}}

    raise DeliveryError(Status.VALIDATION_FAILED, "unbekannter Release-Freigabebefehl")
