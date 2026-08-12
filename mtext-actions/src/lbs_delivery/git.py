"""Stellt die kleine geprüfte Menge der für Lieferungen benötigten Git-Operationen bereit.

Alle Befehle laufen ohne Shell und übersetzen Prozessfehler in das gemeinsame
Lieferfehlermodell. Darauf aufbauende Module können dadurch mit Commits, Tags und
strukturierten Änderungen arbeiten, ohne Git selbst auszuwerten.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .process import DeliveryError, Status


# Reguläre Ausdrücke für Werte an der Git-Grenze.
# Prüft einen vollständigen Release-Tag wie `v261.108` und erfasst beide
# Zahlenteile für den chronologischen Vergleich.
RELEASE_TAG_RE = re.compile(r"v([0-9]{3})\.([0-9]{3})")
# Prüft einen geschützten Branch einer gepflegten Releaselinie und erfasst die
# Releaselinie für die Auswahl des M/Text-Ziels.
RELEASE_BRANCH_RE = re.compile(r"release/(R[0-9]{3})")
# Prüft einen Feature-Branch einschließlich hierarchischer Bezeichnung und
# erfasst die Releaselinie für die Entwicklungssynchronisation.
FEATURE_BRANCH_RE = re.compile(r"feature/(R[0-9]{3})/(.+)")
# Prüft die vom Workflow-Vertrag geforderte vollständige Commit-SHA in
# Kleinbuchstaben. Die vollständige SHA verhindert Mehrdeutigkeit beim Vergleich.
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von `git diff` gemeldete Änderung an einem Repositorypfad.

    Bei Umbenennungen und Kopien bleibt der Quellpfad erhalten, weil der
    DELTA-Paketbau Löschungen von neu angelegten Pfaden unterscheiden muss.
    """

    # Status aus `git diff --name-status`: A, M, D, T, R oder C
    status: str
    # Betroffener Pfad, bei Umbenennung und Kopie das Ziel
    path: str
    # Quellpfad bei Umbenennung und Kopie
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

    # `^{commit}` löst die Referenz bis zum Commit auf und lehnt Tree- und Blob-Objekte ab.
    output = _git(repository, "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    # Git liefert die SHA als ASCII-Bytes, meist mit nachgestelltem Zeilenumbruch.
    value = output.decode("ascii").strip()

    # Nur eine vollständige 40-stellige Hex-SHA weiterverwenden.
    if FULL_SHA_RE.fullmatch(value) is None:
        raise DeliveryError(Status.SOURCE_FAILED, "Git lieferte keine Commit-SHA")

    return value


def require_ancestor(repository: str | Path, ancestor: str, descendant: str) -> None:
    """Fordert, dass ein Commit oder eine Referenz von einer anderen Referenz erreichbar ist.

    Die Lieferworkflows stellen damit sicher, dass ihre Quelle zum erwarteten
    Remote-Branch gehört und nicht lediglich im lokalen Repository vorhanden ist.
    """

    # `--is-ancestor` liefert Exit 0 nur bei echter Abstammung, `_git` wertet den Rückgabecode aus.
    _git(repository, "merge-base", "--is-ancestor", ancestor, descendant)


def read_file(repository: str | Path, commit: str, path: str | Path) -> bytes:
    """Liest eine versionierte Datei aus einem geprüften Commit.

    Diese Git-I/O-Grenze wird beim Wechsel der führenden Releaselinie benötigt,
    um die bisherige Mandantenkonfiguration ohne zweiten Checkout auszuwerten.
    """

    verified_commit = resolve(repository, commit)
    return _git(repository, "show", f"{verified_commit}:{path}")


def resolve_sync_branch(source_branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ordnet einen zulässigen Quellbranch Releaselinie und M/Text-Zielstufe zu.

    `main` und `release/Rnnn` führen zum M/Text-Ziel Funktionstest,
    `feature/Rnnn/<Bezeichnung>` zum M/Text-Ziel Entwicklung. Weitere
    Schrägstriche in der Feature-Bezeichnung sind erlaubt.
    """

    if source_branch == "main":
        return main_releaselinie, "Funktionstest"
    release_match = RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), "Funktionstest"
    feature_match = FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), "Entwicklung"
    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisationszweig")


def require_release_tag(repository: str | Path, tag: str, branches: tuple[str, ...]) -> str:
    """Prüft den Release-Tag-Namen und gibt die zugehörige Commit-SHA zurück.

    Der Tag muss existieren und auf einem der angegebenen geschützten
    Remote-Branches liegen.
    """

    if RELEASE_TAG_RE.fullmatch(tag) is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target = resolve(repository, f"refs/tags/{tag}")
    if resolve(repository, "HEAD") != target:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Tag")
    output = _git(
        repository,
        "for-each-ref",
        "--format=%(refname:short)",
        "--contains",
        target,
        "refs/remotes/origin",
    )
    containing = set(output.decode("utf-8").splitlines())
    if not any(f"origin/{branch}" in containing for branch in branches):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag liegt auf keinem zulässigen Branch")
    return target


def changes(repository: str | Path, base: str, target: str) -> list[GitChange]:
    """Gibt die strukturierten Pfadänderungen zwischen zwei Commits zurück.

    Die nullgetrennte Ausgabe erhält gültige Git-Pfade ohne Mehrdeutigkeit durch
    Quotierung. Die Erkennung von Umbenennungen und Kopien liefert die Angaben
    für korrekte DELTA-Pakete.
    """

    # `git diff --name-status -z --find-renames --find-copies-harder` liefert
    # eine nullgetrennte Liste von Status- und Pfadpaaren für die Änderungen.
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


def project_changes(git_changes: Iterable[GitChange], project: str) -> Iterator[tuple[str, str]]:
    """Überträgt Repositoryänderungen auf die Dateioperationen eines Projekts.

    Umbenennungen werden als Löschung und Hinzufügung ausgegeben, Kopien als
    Hinzufügung. Releasebau und serverSync verwenden damit dieselbe Semantik.
    """

    prefix = f"{project}/"
    for change in git_changes:
        if change.status == "R":
            projected = (("D", change.old_path), ("A", change.path))
        elif change.status == "C":
            projected = (("A", change.path),)
        else:
            projected = ((change.status, change.path),)
        for status, path in projected:
            if path == project or path.startswith(prefix):
                yield status, path


def previous_tag(repository: str | Path, target_tag: str) -> str | None:
    """Ermittelt den numerisch größten Release-Tag vor dem Zieltag.

    Der Lieferbeleg vergleicht den Zieltag mit seinem direkten Release-Vorgänger.
    Dafür zählt die numerische Folge `vnnn.nnn`, nicht die lexikografische
    Sortierung der Tag-Namen in Git.
    """

    target_match = RELEASE_TAG_RE.fullmatch(target_tag)
    if target_match is None:
        raise DeliveryError(Status.VALIDATION_FAILED, "ungültiger Release-Tag")
    target_number = (int(target_match.group(1)), int(target_match.group(2)))

    # Den größten gültigen Tag wählen, der numerisch noch vor dem Zieltag liegt.
    best: tuple[tuple[int, int], str] | None = None
    for tag in _git(repository, "tag", "--list", "v*.*").decode("ascii").splitlines():
        match = RELEASE_TAG_RE.fullmatch(tag)
        if match is None or match.group(1) != target_match.group(1):
            continue
        number = (int(match.group(1)), int(match.group(2)))
        if number < target_number and (best is None or number > best[0]):
            best = (number, tag)
    return best[1] if best else None
