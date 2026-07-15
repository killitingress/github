"""Löst Git-Referenzen sicher auf und wertet Änderungen reproduzierbar aus."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import DeliveryError, Status


_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_TAG_RE = re.compile(r"R([0-9]{3})\.([0-9]{3})")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von Git gemeldete Dateiänderung."""

    status: str
    path: str
    old_path: str | None = None


def _git(repository: str | Path, *arguments: str) -> bytes:
    """Führt einen lesenden Git-Aufruf mit vereinheitlichter Fehlerbehandlung aus."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "git is not available") from exc
    if result.returncode != 0:
        raise DeliveryError(Status.SOURCE_FAILED, "git reference operation failed")
    return result.stdout


def require_full_sha(value: str) -> str:
    """Akzeptiert ausschließlich vollständige, kleingeschriebene Commit-SHAs."""

    if _FULL_SHA_RE.fullmatch(value) is None:
        raise DeliveryError(Status.SOURCE_FAILED, "commit must be a full SHA")
    return value


def resolve_commit(repository: str | Path, reference: str) -> str:
    """Löst eine Git-Referenz eindeutig auf den zugehörigen Commit auf."""

    if not reference or reference.startswith("-"):
        raise DeliveryError(Status.SOURCE_FAILED, "invalid git reference")
    resolved = _git(repository, "rev-parse", "--verify", f"{reference}^{{commit}}")
    value = resolved.decode("ascii", errors="strict").strip()
    return require_full_sha(value)


def require_head(repository: str | Path, expected_sha: str) -> None:
    """Stellt sicher, dass der ausgecheckte Stand dem erwarteten Commit entspricht."""

    if resolve_commit(repository, "HEAD") != require_full_sha(expected_sha):
        raise DeliveryError(
            Status.SOURCE_FAILED, "checked out HEAD does not match requested commit"
        )


def require_commit_on_branch(
    repository: str | Path, commit_sha: str, branch: str
) -> None:
    """Prüft, dass ein Commit vom ausgewählten Remote-Branch erreichbar ist."""

    commit = require_full_sha(commit_sha)
    if not is_ancestor(repository, commit, f"refs/remotes/origin/{branch}"):
        raise DeliveryError(
            Status.SOURCE_FAILED,
            "requested commit is not reachable from the selected stage branch",
        )


def is_ancestor(repository: str | Path, ancestor: str, descendant: str) -> bool:
    """Prüft über Git, ob ein Commit Vorfahr einer zweiten Referenz ist."""

    ancestor_sha = resolve_commit(repository, ancestor)
    descendant_sha = resolve_commit(repository, descendant)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            ancestor_sha,
            descendant_sha,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise DeliveryError(Status.SOURCE_FAILED, "git ancestry check failed")


def require_tag_on_branch(
    repository: str | Path, tag: str, required_branch: str
) -> str:
    """Löst einen Release-Tag auf und prüft seine Erreichbarkeit vom Zielbranch."""

    tag_sha = resolve_commit(repository, f"refs/tags/{tag}")
    branch_sha = resolve_commit(repository, f"refs/remotes/origin/{required_branch}")
    if not is_ancestor(repository, tag_sha, branch_sha):
        raise DeliveryError(
            Status.SOURCE_FAILED, "release tag is not reachable from required branch"
        )
    return tag_sha


def diff_name_status(
    repository: str | Path, base_sha: str, target_sha: str
) -> list[GitChange]:
    """Liest Dateiänderungen zwischen zwei Commits einschließlich Umbenennungen."""

    base = require_full_sha(base_sha)
    target = require_full_sha(target_sha)
    fields = _git(
        repository, "diff", "--name-status", "-z", "--find-renames", base, target
    ).decode("utf-8", errors="strict").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    changes: list[GitChange] = []
    index = 0
    while index < len(fields):
        status_field = fields[index]
        index += 1
        status = status_field[0]
        if status in {"R", "C"}:
            if index + 1 >= len(fields):
                raise DeliveryError(Status.SOURCE_FAILED, "malformed git rename diff")
            old_path, new_path = fields[index], fields[index + 1]
            index += 2
            changes.append(GitChange(status=status, path=new_path, old_path=old_path))
        else:
            if index >= len(fields):
                raise DeliveryError(Status.SOURCE_FAILED, "malformed git diff")
            changes.append(GitChange(status=status, path=fields[index]))
            index += 1
    return changes


def previous_release_tag(repository: str | Path, target_tag: str) -> str | None:
    """Ermittelt den numerisch letzten Release-Tag vor dem Zieltag."""

    match = _TAG_RE.fullmatch(target_tag)
    if match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "invalid release tag")
    target = (int(match.group(1)), int(match.group(2)))
    tags = _git(repository, "tag", "--list", "R[0-9][0-9][0-9].[0-9][0-9][0-9]")
    candidates: list[tuple[tuple[int, int], str]] = []
    for tag in tags.decode("ascii", errors="strict").splitlines():
        candidate = _TAG_RE.fullmatch(tag)
        if candidate is None:
            continue
        numeric = (int(candidate.group(1)), int(candidate.group(2)))
        if numeric < target:
            candidates.append((numeric, tag))
    return max(candidates)[1] if candidates else None
