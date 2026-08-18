"""Bereitet den Vier-Augen-Nachweis für reguläre Releases vor und prüft ihn.

Der Freigabe-Pull-Request nimmt eine JSON-Datei in den Lieferbranch auf. Sie
bindet Release-Version, Branch, Commit und Elementlisten aneinander. Der
Release-Tag entsteht auf dem Merge-Commit des Pull Requests. Damit liegt der
Nachweis im getaggten Stand, und der Releasebau kann ihn dort lesen und gegen
den freigegebenen Lieferumfang prüfen.

Den Pull Request eröffnet der Antragsteller selbst. Er ist damit dessen Autor,
und GitHub lässt niemanden den eigenen Pull Request genehmigen. Das
Vier-Augen-Prinzip erzwingen so die Schutzregeln des Lieferbranches.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import config, git, github
from .config import Configuration, MANDANT_CONFIG_PATH, release_branches
from .process import DeliveryError, Status
from .project_package import package_stand, project_elements, release_scope


# Freigabeanforderungen liegen im Lieferbranch und bilden dort den prüfbaren
# Nachweis des zusammengeführten Freigabe-Pull-Requests.
APPROVAL_ROOT = Path(".github/release-approvals")

# Technisch erzeugte Branches heißen `release-approval/<Release-Tag>/<Lauf>`.
# Das Präfix unterscheidet sie von anderen Pull Requests, und der Abschluss
# liest den Release-Tag wieder aus dem Namen.
APPROVAL_BRANCH_PREFIX = "release-approval/"


@dataclass(frozen=True)
class PullRequestMerge:
    """Beschreibt die für den Freigabeabschluss relevanten Pull-Request-Daten."""

    # GitHub meldet diesen Commit als Ergebnis des Pull-Request-Merge.
    merge_sha: str
    # Der Pull Request muss in diesem Lieferbranch gelandet sein.
    branch: str
    # Dieser technische Branch enthält den Freigabenachweis.
    approval_branch: str


def approval_path(tag: str) -> Path:
    """Gibt den versionierten Pfad der Freigabeanforderung eines Tags zurück."""

    return APPROVAL_ROOT / f"{tag}.json"


def _approval_document(
    configuration: Configuration,
    repository_root: str | Path,
    *,
    tag: str,
    branch: str,
    target_sha: str,
) -> dict[str, object]:
    """Erstellt den erwarteten Freigabenachweis aus dem angegebenen Git-Stand.

    Die Feldstruktur ist der verbindliche Integritätsvertrag. Jede Änderung an
    Feldern, Reihenfolge der Projekte oder Elementlisten bricht den Vergleich
    mit bereits geschriebenen Freigaben und muss als Schemaänderung behandelt
    werden.
    """

    base, changes = release_scope(repository_root, tag, target_sha)
    return {
        "release": tag,
        "branch": branch,
        "commit": target_sha,
        "projekte": [
            {
                "projekt": project,
                "stand": package_stand(base=base, target=(tag, target_sha)),
                "elemente": project_elements(
                    repository_root,
                    project,
                    base=base,
                    changes=changes,
                ),
            }
            for project in configuration.projects
        ],
    }


def _read_document(content: bytes | str) -> dict[str, object]:
    """Liest eine Freigabeanforderung und lehnt ungültiges JSON ab."""

    try:
        document = json.loads(content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe ist ungültig") from exc
    if not isinstance(document, dict):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe ist ungültig")
    return document


def _regular_release_tag(tag: str, failure: Status, message: str) -> str:
    """Liest die Releaselinie eines regulären Release-Tags."""

    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None or tag_match.group("beta_suffix"):
        raise DeliveryError(failure, message)
    return f"R{tag_match.group('releaselinie')}"


def _require_release_branch(
    configuration: Configuration, branch: str, releaselinie: str, failure: Status, message: str
) -> None:
    """Prüft die Zuordnung eines Lieferbranches zur Releaselinie."""

    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(failure, "Releaselinie ist unbekannt")
    if branch not in release_branches(configuration, releaselinie):
        raise DeliveryError(failure, message)


def _pull_request_merge(pull_request: dict[str, object]) -> PullRequestMerge:
    """Liest die für den Freigabeabschluss erforderlichen GitHub-Daten."""

    match pull_request:
        case {
            "merged": True,
            "merge_commit_sha": str(merge_sha),
            "base": {"ref": str(branch)},
            "head": {"ref": str(approval_branch)},
        }:
            return PullRequestMerge(merge_sha, branch, approval_branch)
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist nicht zusammengeführt")


def _verify_approval_delivery(
    configuration: Configuration,
    repository_root: str | Path,
    document: dict[str, object],
    *,
    tag: str,
    branch: str,
    approved_sha: str,
    target_sha: str,
) -> None:
    """Prüft den Nachweis gegen den freigegebenen Lieferumfang am Ziel-Commit."""

    git.require_ancestor(repository_root, approved_sha, target_sha)
    # Zwischen Freigabe und Tag darf nur der Nachweis unter .github hinzukommen.
    changes = git.changes(repository_root, approved_sha, target_sha)
    for relevant in (MANDANT_CONFIG_PATH.as_posix(), *configuration.projects):
        if any(git.project_changes(changes, relevant)):
            raise DeliveryError(Status.SOURCE_FAILED, "Lieferstand hat sich nach der Freigabe geändert")
    expected = _approval_document(
        configuration,
        repository_root,
        tag=tag,
        branch=branch,
        target_sha=approved_sha,
    )
    if document != expected:
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe passt nicht zum Lieferumfang")


def prepare_release_approval(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    tag: str,
    branch: str,
    source_sha: str,
    run_reference: str,
) -> tuple[str, Path]:
    """Schreibt die Freigabeanforderung und benennt den technischen Branch.

    `run_reference` bezeichnet Lauf und Versuch des Workflows und hält
    wiederholte Vorbereitungen desselben Release-Tags auseinander.
    """

    root = Path(repository_root)
    releaselinie = _regular_release_tag(tag, Status.VALIDATION_FAILED, "Freigabe-PR benötigt einen regulären Release-Tag")
    _require_release_branch(configuration, branch, releaselinie, Status.SOURCE_FAILED, "Branch passt nicht zur Release-Version")
    if git.resolve(root, "HEAD") != source_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum ausgewählten Branchstand")
    if git.resolve(root, f"refs/remotes/origin/{branch}") != source_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "ausgewählter Branchstand ist nicht mehr aktuell")
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag ist bereits vorhanden")

    path = root / approval_path(tag)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _approval_document(
                    configuration,
                    root,
                    tag=tag,
                    branch=branch,
                    target_sha=source_sha,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise DeliveryError(Status.PACKAGE_FAILED, "Release-Freigabe kann nicht geschrieben werden") from exc

    return f"{APPROVAL_BRANCH_PREFIX}{tag}/{run_reference}", path


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

    # Die GitHub-Daten müssen denselben Merge, Zielbranch und Freigabe-Branch
    # belegen, die der Mandanten-Workflow gemeldet hat.
    merge = _pull_request_merge(pull_request)
    if merge.merge_sha != merge_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request nennt einen anderen Merge-Commit")
    if merge.branch != branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request wurde in einen anderen Branch zusammengeführt")
    if merge.approval_branch != approval_branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request gehört zu einem anderen Freigabe-Branch")

    if not approval_branch.startswith(APPROVAL_BRANCH_PREFIX):
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist keine Release-Freigabe")
    tag = approval_branch.removeprefix(APPROVAL_BRANCH_PREFIX).split("/", 1)[0]
    releaselinie = _regular_release_tag(tag, Status.SOURCE_FAILED, "Freigabe-Branch enthält keinen regulären Release-Tag")
    _require_release_branch(configuration, branch, releaselinie, Status.SOURCE_FAILED, "Zielbranch passt nicht zur Release-Version")
    if git.resolve(root, "HEAD") != merge_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Freigabe-Merge")

    path = root / approval_path(tag)
    try:
        document = _read_document(path.read_bytes())
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe fehlt") from exc
    match document:
        case {"commit": str(approved_sha)}:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe ist unvollständig")

    _verify_approval_delivery(
        configuration,
        root,
        document,
        tag=tag,
        branch=branch,
        approved_sha=approved_sha,
        target_sha=merge_sha,
    )
    if git.reference_exists(root, f"refs/tags/{tag}"):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag ist bereits vorhanden")
    return tag


def require_release_approval(
    configuration: Configuration,
    *,
    repository_root: str | Path,
    tag: str,
    target_sha: str,
    branches: tuple[str, ...],
) -> None:
    """Fordert den im getaggten Stand enthaltenen Freigabenachweis.

    Der reguläre Release-Tag zeigt auf den Merge-Commit des Freigabe-Pull-
    Requests. Der Nachweis liegt deshalb im getaggten Baum und benennt den
    Commit, den die zweite Person geprüft hat.
    """

    root = Path(repository_root)
    try:
        content = git.read_file(root, target_sha, approval_path(tag))
    except DeliveryError as exc:
        # Der getaggte Baum enthält den Nachweis nicht, der Tag ist also nicht
        # aus einem zusammengeführten Freigabe-Pull-Request entstanden.
        raise DeliveryError(Status.SOURCE_FAILED, "regulärer Release-Tag besitzt keine PR-Freigabe") from exc

    document = _read_document(content)
    match document:
        case {"branch": str(branch), "commit": str(approved_sha)}:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe ist unvollständig")
    if branch not in branches:
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe nennt keinen zulässigen Lieferbranch")

    _verify_approval_delivery(
        configuration,
        root,
        document,
        tag=tag,
        branch=branch,
        approved_sha=approved_sha,
        target_sha=target_sha,
    )


def run_command(arguments: argparse.Namespace) -> dict[str, object]:
    """Bereitet die Release-Freigabe vor oder prüft ihren Merge."""

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
