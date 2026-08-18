"""Liest die für Synchronisation und Release benötigten Angaben aus Git.

Das Modul löst Referenzen in Commit-SHAs auf, prüft Tags und Branchbeziehungen
und liefert Dateiänderungen für den Paketbau und die Synchronisation.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .config import MTEXT_ZIEL_ENTWICKLUNG, MTEXT_ZIEL_FUNKTIONSTEST
from .process import DeliveryError, Status


# Reguläre Ausdrücke prüfen die von Git und den Workflows gelieferten Namen.
# Prüft einen vollständigen Release-Tag wie `v261.108` oder den Stand einer
# Beta-Lieferung wie `v261.108a` und erfasst seine fachlichen Bestandteile.
RELEASE_TAG_RE = re.compile(
    r"v(?P<releaselinie>[0-9]{3})\.(?P<release>[0-9]{3})(?P<beta_suffix>[a-zA-Z]?)"
)

# Prüft einen geschützten Branch einer gepflegten Releaselinie und erfasst die
# Releaselinie für die Auswahl des M/Text-Ziels.
RELEASE_BRANCH_RE = re.compile(r"release/(R[0-9]{3})")

# Prüft einen Feature-Branch einschließlich hierarchischer Bezeichnung und
# erfasst die Releaselinie für die Entwicklungssynchronisation.
FEATURE_BRANCH_RE = re.compile(r"feature/(R[0-9]{3})/(.+)")


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von `git diff` gemeldete Änderung an einem Repositorypfad."""

    # Status aus `git diff --name-status`: A, M, D oder T
    status: str
    # Betroffener Repositorypfad
    path: str


def _git(repository: str | Path, *arguments: str, returncodes: tuple[int, ...] = (0,)) -> bytes:
    """Führt einen Git-Befehl aus und gibt seine Standardausgabe zurück.

    Bei einem unerwarteten Rückgabecode wird der Schritt mit `SOURCE_FAILED`
    beendet.
    """

    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode not in returncodes:
        raise DeliveryError(Status.SOURCE_FAILED, "Git-Operation fehlgeschlagen")

    return result.stdout


def resolve(repository: str | Path, reference: str) -> str:
    """Löst eine bekannte Referenz in eine vollständige Commit-SHA auf."""

    # `^{commit}` löst die Referenz bis zum Commit auf und lehnt Tree- und Blob-Objekte ab.
    output = _git(repository, "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    return output.decode("ascii").strip()


def reference_exists(repository: str | Path, reference: str) -> bool:
    """Prüft, ob eine vollständige Git-Referenz vorhanden ist."""

    output = _git(
        repository,
        "show-ref",
        "--verify",
        reference,
        returncodes=(0, 128),
    )
    return bool(output)


def require_ancestor(repository: str | Path, ancestor: str, descendant: str) -> None:
    """Fordert, dass ein Commit oder eine Referenz von einer anderen Referenz erreichbar ist.

    Damit lässt sich prüfen, ob ein Commit zum erwarteten Remote-Branch gehört
    oder ob ein Basistag vor dem Release-Tag liegt.
    """

    # `--is-ancestor` liefert Exit 0 nur bei echter Abstammung
    _git(repository, "merge-base", "--is-ancestor", ancestor, descendant)


def read_file(repository: str | Path, commit: str, path: str | Path) -> bytes:
    """Liest eine Datei aus einem bestimmten Commit.

    Beim Wechsel der führenden Releaselinie wird damit die bisherige
    Mandantenkonfiguration ohne zweiten Checkout gelesen.
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
        return main_releaselinie, MTEXT_ZIEL_FUNKTIONSTEST

    release_match = RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), MTEXT_ZIEL_FUNKTIONSTEST

    feature_match = FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), MTEXT_ZIEL_ENTWICKLUNG

    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisationszweig")


def require_release_commit(repository: str | Path, tag: str, branches: tuple[str, ...]) -> str:
    """Gibt den Commit eines Release-Tags zurück und prüft seine Herkunft.

    Checkout und Tag müssen auf denselben Commit zeigen. Dieser Commit muss auf
    einem der angegebenen Remote-Branches liegen.
    """

    target = resolve(repository, f"refs/tags/{tag}")
    if resolve(repository, "HEAD") != target:
        raise DeliveryError(Status.SOURCE_FAILED, "Checkout stimmt nicht zum Tag")

    output = _git(
        repository,
        "for-each-ref",  # nur die angegebenen Referenzen unter `refs/remotes/origin`
        "--format=%(refname:short)",  # Kurzname, zum Beispiel `origin/main`
        "--contains",  # nur Branches, deren Historie den Tag-Commit bereits enthält
        target,
        "refs/remotes/origin",  # Remote-Tracking-Branches, keine Tags
    )

    containing = set(output.decode().splitlines())

    if not any(f"origin/{branch}" in containing for branch in branches):
        raise DeliveryError(Status.SOURCE_FAILED, "Release-Tag liegt auf keinem zulässigen Branch")

    return target


def changes(repository: str | Path, base: str, target: str) -> list[GitChange]:
    """Gibt Status und Pfade der Änderungen zwischen zwei Commits zurück.

    Die nullgetrennte Ausgabe erhält gültige Git-Pfade ohne Mehrdeutigkeit durch
    Quotierung. Git gibt Umbenennungen als Löschung und Hinzufügung aus, weil
    DELTA-Pakete und serverSync genau diese Dateioperationen benötigen.
    """

    # `--no-renames` liefert Umbenennungen direkt als Löschung und Hinzufügung,
    # so wie wir es für DELTA-Pakete und serverSync benötigen.
    output = _git(
        repository,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        base,
        target,
    )
    data = output.decode().rstrip("\0")
    if not data:
        return []

    # Git liefert Status und Pfad als aufeinanderfolgende NUL-getrennte Felder.
    fields = iter(data.split("\0"))
    return [GitChange(status_field[0], next(fields)) for status_field in fields]


def project_changes(git_changes: Iterable[GitChange], project: str) -> Iterator[tuple[str, str]]:
    """Gibt die Dateiänderungen eines Projekts zurück."""

    prefix = f"{project}/"
    for change in git_changes:
        if change.path == project or change.path.startswith(prefix):
            yield change.status, change.path
