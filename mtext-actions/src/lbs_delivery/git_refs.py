"""Löst Git-Referenzen sicher auf und wertet Änderungen reproduzierbar aus."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import RELEASE_TAG_RE
from .errors import DeliveryError, Status


# Reguläre Ausdrücke für Git-Referenzen.
# Prüft eine vollständige kleingeschriebene Commit-SHA.
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von Git gemeldete Dateiänderung."""

    status: str
    path: str
    old_path: str | None = None


def _git(
    repository: str | Path,
    *arguments: str,
    accepted_returncodes: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[bytes]:
    """Führt Git mit vereinheitlichter Prozess- und Fehlerbehandlung aus."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "Git ist nicht verfügbar") from exc
    if result.returncode not in accepted_returncodes:
        raise DeliveryError(
            Status.SOURCE_FAILED, "Git-Referenzoperation fehlgeschlagen"
        )
    return result


def require_full_sha(value: str) -> str:
    """Akzeptiert ausschließlich vollständige, kleingeschriebene Commit-SHAs."""

    if FULL_SHA_RE.fullmatch(value) is None:
        raise DeliveryError(
            Status.SOURCE_FAILED, "Commit benötigt eine vollständige SHA"
        )
    return value


def resolve_commit(repository: str | Path, reference: str) -> str:
    """Löst eine Git-Referenz eindeutig auf den zugehörigen Commit auf."""

    if not reference or reference.startswith("-"):
        raise DeliveryError(Status.SOURCE_FAILED, "ungültige Git-Referenz")
    result = _git(repository, "rev-parse", "--verify", f"{reference}^{{commit}}")
    value = result.stdout.decode("ascii", errors="strict").strip()
    return require_full_sha(value)


def require_head(repository: str | Path, expected_sha: str) -> None:
    """Stellt sicher, dass der ausgecheckte Stand dem erwarteten Commit entspricht."""

    if resolve_commit(repository, "HEAD") != require_full_sha(expected_sha):
        raise DeliveryError(
            Status.SOURCE_FAILED,
            "ausgecheckter HEAD stimmt nicht mit dem angeforderten Commit überein",
        )


def require_commit_on_branch(
    repository: str | Path, commit_sha: str, branch: str
) -> None:
    """Prüft, dass ein Commit vom ausgewählten Remote-Branch erreichbar ist."""

    commit = require_full_sha(commit_sha)
    if not is_ancestor(repository, commit, f"refs/remotes/origin/{branch}"):
        raise DeliveryError(
            Status.SOURCE_FAILED,
            "Commit ist vom ausgewählten Stage-Branch nicht erreichbar",
        )


def is_ancestor(repository: str | Path, ancestor: str, descendant: str) -> bool:
    """Prüft über Git, ob ein Commit Vorfahr einer zweiten Referenz ist."""

    ancestor_sha = resolve_commit(repository, ancestor)
    descendant_sha = resolve_commit(repository, descendant)
    result = _git(
        repository,
        "merge-base",
        "--is-ancestor",
        ancestor_sha,
        descendant_sha,
        accepted_returncodes=(0, 1),
    )
    return result.returncode == 0


def require_tag_on_branch(
    repository: str | Path, tag: str, required_branch: str
) -> str:
    """Löst einen Release-Tag auf und prüft seine Erreichbarkeit vom Zielbranch."""

    tag_sha = resolve_commit(repository, f"refs/tags/{tag}")
    branch_sha = resolve_commit(repository, f"refs/remotes/origin/{required_branch}")
    if not is_ancestor(repository, tag_sha, branch_sha):
        raise DeliveryError(
            Status.SOURCE_FAILED,
            "Release-Tag ist vom erforderlichen Branch nicht erreichbar",
        )
    return tag_sha


def diff_name_status(
    repository: str | Path, base_sha: str, target_sha: str
) -> list[GitChange]:
    """Liest Dateiänderungen zwischen zwei Commits einschließlich Umbenennungen."""

    base = require_full_sha(base_sha)
    target = require_full_sha(target_sha)
    result = _git(
        repository, "diff", "--name-status", "-z", "--find-renames", base, target
    )
    fields = result.stdout.decode("utf-8", errors="strict").split("\0")
    # Die Nulltrennung erhält auch ungewöhnliche, aber gültige Dateinamen
    # unverändert.
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
                raise DeliveryError(
                    Status.SOURCE_FAILED, "fehlerhafter Git-Diff für eine Umbenennung"
                )
            old_path, new_path = fields[index], fields[index + 1]
            index += 2
            changes.append(GitChange(status=status, path=new_path, old_path=old_path))
        else:
            if index >= len(fields):
                raise DeliveryError(Status.SOURCE_FAILED, "fehlerhafter Git-Diff")
            changes.append(GitChange(status=status, path=fields[index]))
            index += 1
    return changes


def previous_release_tag(repository: str | Path, target_tag: str) -> str | None:
    """Ermittelt den numerisch letzten Release-Tag vor dem Zieltag."""

    match = RELEASE_TAG_RE.fullmatch(target_tag)
    if match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target = (int(match.group(1)), int(match.group(2)))
    # Git verwendet hier ein Glob; die Treffer werden danach erneut mit dem
    # regulären Ausdruck geprüft.
    result = _git(
        repository, "tag", "--list", "R[0-9][0-9][0-9].[0-9][0-9][0-9]"
    )
    candidates: list[tuple[tuple[int, int], str]] = []
    for tag in result.stdout.decode("ascii", errors="strict").splitlines():
        candidate = RELEASE_TAG_RE.fullmatch(tag)
        if candidate is None:
            continue
        numeric = (int(candidate.group(1)), int(candidate.group(2)))
        if numeric < target:
            candidates.append((numeric, tag))
    return max(candidates)[1] if candidates else None
