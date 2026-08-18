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

import json
import urllib.parse
from pathlib import Path

from . import git, github_api
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


def _require_unchanged_delivery(
    configuration: Configuration,
    repository_root: str | Path,
    *,
    approved_sha: str,
    target_sha: str,
) -> None:
    """Fordert, dass nach dem freigegebenen Commit kein Lieferinhalt geändert wurde.

    Zwischen dem geprüften Stand und dem getaggten Merge-Commit darf nur der
    Nachweis unter `.github` hinzukommen. Eine Änderung an der
    Mandantenkonfiguration oder an einem Projekt würde einen anderen
    Lieferumfang ergeben als den, den die zweite Person geprüft hat.
    """

    changes = git.changes(repository_root, approved_sha, target_sha)
    for relevant in (MANDANT_CONFIG_PATH.as_posix(), *configuration.projects):
        if any(git.project_changes(changes, relevant)):
            raise DeliveryError(Status.SOURCE_FAILED, "Lieferstand hat sich nach der Freigabe geändert")


def _canonical_document(document: dict[str, object]) -> str:
    """Serialisiert einen Freigabenachweis für den Integritätsvergleich."""

    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    _require_unchanged_delivery(
        configuration,
        repository_root,
        approved_sha=approved_sha,
        target_sha=target_sha,
    )
    expected = _approval_document(
        configuration,
        repository_root,
        tag=tag,
        branch=branch,
        target_sha=approved_sha,
    )
    if _canonical_document(document) != _canonical_document(expected):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Freigabe passt nicht zum Lieferumfang")


def read_pull_request(
    *,
    api_url: str,
    repository: str,
    number: int,
    token: str,
) -> dict[str, object]:
    """Liest den gemergten Pull Request als Sicherheitsgrenze von GitHub."""

    document = github_api.request(
        method="GET",
        url=f"{api_url.rstrip('/')}/repos/{urllib.parse.quote(repository, safe='/')}/pulls/{number}",
        token=token,
        failure=Status.SOURCE_FAILED,
    )
    if not isinstance(document, dict):
        raise DeliveryError(Status.SOURCE_FAILED, "GitHub-Antwort zum Pull Request ist ungültig")
    return document


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
    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None or tag_match.group("beta_suffix"):
        raise DeliveryError(Status.VALIDATION_FAILED, "Freigabe-PR benötigt einen regulären Release-Tag")

    releaselinie = f"R{tag_match.group('releaselinie')}"
    if releaselinie not in configuration.releaselinien:
        raise DeliveryError(Status.VALIDATION_FAILED, "Releaselinie ist unbekannt")
    if branch not in release_branches(configuration, releaselinie):
        raise DeliveryError(Status.SOURCE_FAILED, "Branch passt nicht zur Release-Version")
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
    match pull_request:
        case {
            "merged": True,
            "merge_commit_sha": str(merged_commit),
            "base": {"ref": str(base_branch)},
            "head": {"ref": str(head_branch)},
        }:
            pass
        case _:
            raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist nicht zusammengeführt")
    if merged_commit != merge_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request nennt einen anderen Merge-Commit")
    if base_branch != branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request wurde in einen anderen Branch zusammengeführt")
    if head_branch != approval_branch:
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request gehört zu einem anderen Freigabe-Branch")

    if not approval_branch.startswith(APPROVAL_BRANCH_PREFIX):
        raise DeliveryError(Status.SOURCE_FAILED, "Pull Request ist keine Release-Freigabe")
    tag = approval_branch.removeprefix(APPROVAL_BRANCH_PREFIX).split("/", 1)[0]
    tag_match = git.RELEASE_TAG_RE.fullmatch(tag)
    if tag_match is None or tag_match.group("beta_suffix"):
        raise DeliveryError(Status.SOURCE_FAILED, "Freigabe-Branch enthält keinen regulären Release-Tag")

    releaselinie = f"R{tag_match.group('releaselinie')}"
    if branch not in release_branches(configuration, releaselinie):
        raise DeliveryError(Status.SOURCE_FAILED, "Zielbranch passt nicht zur Release-Version")
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
