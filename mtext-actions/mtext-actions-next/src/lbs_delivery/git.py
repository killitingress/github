"""Kapselt die wenigen benötigten Git-Abfragen."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import DeliveryError, Status


# Reguläre Ausdrücke für Eingaben an Git.
# Prüft einen Release-Tag wie `R261.108` und stellt seine Zahlen bereit.
RELEASE_TAG_RE = re.compile(r"R([0-9]{3})\.([0-9]{3})")
# Prüft die vom Workflow verlangte vollständige Commit-SHA.
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt einen geänderten Repositorypfad."""

    status: str
    path: str
    old_path: str | None = None


def _git(
    repository: str | Path,
    *arguments: str,
    returncodes: tuple[int, ...] = (0,),
) -> bytes:
    """Führt Git aus und behandelt dessen Prozessstatus als Systemgrenze."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, "Git ist nicht verfügbar") from exc
    if result.returncode not in returncodes:
        raise DeliveryError(Status.SOURCE_FAILED, "Git-Operation fehlgeschlagen")
    return result.stdout


def resolve(repository: str | Path, reference: str) -> str:
    """Löst eine bekannte Referenz auf genau einen Commit auf."""

    value = _git(
        repository,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{reference}^{{commit}}",
    ).decode("ascii").strip()
    if FULL_SHA_RE.fullmatch(value) is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Git lieferte keine Commit-SHA")
    return value


def require_checkout(repository: str | Path, commit: str, branch: str) -> None:
    """Prüft Commitformat, Checkout und Erreichbarkeit vom Zielbranch."""

    if FULL_SHA_RE.fullmatch(commit) is None or resolve(repository, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    _git(
        repository,
        "merge-base",
        "--is-ancestor",
        commit,
        f"refs/remotes/origin/{branch}",
    )


def require_release_tag(repository: str | Path, tag: str, branch: str) -> str:
    """Prüft Tagformat, Checkout und Erreichbarkeit vom Bereitstellungsbranch."""

    if RELEASE_TAG_RE.fullmatch(tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target = resolve(repository, f"refs/tags/{tag}")
    if resolve(repository, "HEAD") != target:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Tag")
    _git(
        repository,
        "merge-base",
        "--is-ancestor",
        target,
        f"refs/remotes/origin/{branch}",
    )
    return target


def changes(repository: str | Path, base: str, target: str) -> list[GitChange]:
    """Liest den nullgetrennten Git-Diff einschließlich Umbenennungen und Kopien."""

    output = _git(
        repository,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        "--find-copies-harder",
        base,
        target,
    )
    data = output.decode("utf-8").rstrip("\0")
    if not data:
        return []
    fields = iter(data.split("\0"))
    result: list[GitChange] = []
    for status_field in fields:
        status = status_field[0]
        if status in {"R", "C"}:
            old_path = next(fields)
            result.append(GitChange(status, next(fields), old_path))
        else:
            result.append(GitChange(status, next(fields)))
    return result


def previous_tag(repository: str | Path, target_tag: str) -> str | None:
    """Ermittelt den numerisch letzten Release-Tag vor dem Zieltag."""

    target_match = RELEASE_TAG_RE.fullmatch(target_tag)
    if target_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target = (int(target_match.group(1)), int(target_match.group(2)))
    candidates: list[tuple[tuple[int, int], str]] = []
    for tag in _git(repository, "tag", "--list", "R*.*").decode("ascii").splitlines():
        match = RELEASE_TAG_RE.fullmatch(tag)
        if match:
            numeric = (int(match.group(1)), int(match.group(2)))
            if numeric < target:
                candidates.append((numeric, tag))
    return max(candidates)[1] if candidates else None
