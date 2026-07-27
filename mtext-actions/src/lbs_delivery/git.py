"""Stellt die kleine geprüfte Menge der für Lieferungen benötigten Git-Operationen bereit.

Alle Befehle laufen ohne Shell und übersetzen Prozessfehler in das gemeinsame
Lieferfehlermodell. Darauf aufbauende Module können dadurch mit Commits, Tags und
strukturierten Änderungen arbeiten, ohne Git selbst auszuwerten.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .process import DeliveryError, Status


# Reguläre Ausdrücke für Werte an der Git-Grenze.
# Prüft einen vollständigen Release-Tag wie `R261.108` und erfasst beide
# Zahlenteile für den chronologischen Vergleich.
RELEASE_TAG_RE = re.compile(r"R([0-9]{3})\.([0-9]{3})")
# Prüft die vom Workflow-Vertrag geforderte vollständige Commit-SHA in
# Kleinbuchstaben. Die vollständige SHA verhindert Mehrdeutigkeit beim Vergleich.
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von `git diff` gemeldete Änderung an einem Repositorypfad.

    Bei Umbenennungen und Kopien bleibt der Quellpfad erhalten, weil der
    DELTA-Paketbau Löschungen von neu angelegten Pfaden unterscheiden muss.
    """

    status: str
    path: str
    old_path: str | None = None


def _git(repository: str | Path, *arguments: str, returncodes: tuple[int, ...] = (0,)) -> bytes:
    """Führt einen Git-Befehl aus und prüft seinen Rückgabecode.

    Beide Ausgabeströme werden aufgefangen, damit rohe Git-Diagnosen nicht in die
    stabile Workflow-Schnittstelle gelangen. stdout bleibt für die geprüfte
    Auswertung erhalten.
    """

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
    """Löst eine bekannte Referenz in eine vollständige Commit-SHA auf.

    Die ausdrückliche Commit-Auflösung lehnt andere Git-Objekte ab. Die
    Formatprüfung verhindert, dass unerwartete Git-Ausgaben in spätere
    Vergleiche gelangen.
    """

    output = _git(repository, "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    value = output.decode("ascii").strip()
    if FULL_SHA_RE.fullmatch(value) is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Git lieferte keine Commit-SHA")
    return value


def require_ancestor(repository: str | Path, ancestor: str, descendant: str) -> None:
    """Fordert, dass ein Commit oder eine Referenz von einer anderen Referenz erreichbar ist.

    Die Lieferworkflows stellen damit sicher, dass ihre Quelle zum erwarteten
    Remote-Branch gehört und nicht lediglich im lokalen Repository vorhanden ist.
    """

    _git(repository, "merge-base", "--is-ancestor", ancestor, descendant)


def require_checkout(repository: str | Path, commit: str, branch: str) -> None:
    """Prüft einen durch Commit ausgelösten Checkout gegen seinen Zielbranch.

    Sowohl HEAD als auch die Abstammung vom Remote-Branch werden geprüft. So kann
    keine gültige SHA aus einer fremden Historie synchronisiert werden.
    """

    if FULL_SHA_RE.fullmatch(commit) is None or resolve(repository, "HEAD") != commit:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Commit")
    require_ancestor(repository, commit, f"refs/remotes/origin/{branch}")


def require_release_tag(repository: str | Path, tag: str, branch: str) -> str:
    """Prüft einen Release-Tag und gibt den ausgecheckten Commit zurück.

    Vor dem Paketbau muss der Tag dem Namensvertrag entsprechen, auf HEAD zeigen
    und vom vorgesehenen Bereitstellungsbranch erreichbar sein.
    """

    if RELEASE_TAG_RE.fullmatch(tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target = resolve(repository, f"refs/tags/{tag}")
    if resolve(repository, "HEAD") != target:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Tag")
    require_ancestor(repository, target, f"refs/remotes/origin/{branch}")
    return target


def changes(repository: str | Path, base: str, target: str) -> list[GitChange]:
    """Gibt die strukturierten Pfadänderungen zwischen zwei Commits zurück.

    Die nullgetrennte Ausgabe erhält gültige Git-Pfade ohne Mehrdeutigkeit durch
    Quotierung. Die Erkennung von Umbenennungen und Kopien liefert die Angaben
    für korrekte DELTA-Pakete.
    """

    output = _git(repository, "diff", "--name-status", "-z", "--find-renames", "--find-copies-harder", base, target)
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
    """Ermittelt den numerisch größten Release-Tag vor dem Zieltag.

    Der numerische Vergleich vermeidet Fehler einer lexikografischen Sortierung
    und ignoriert Tags außerhalb des Release-Namensvertrags.
    """

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
