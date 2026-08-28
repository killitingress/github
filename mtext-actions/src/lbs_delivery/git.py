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
# Prüft einen Lieferstand aus Hauptrelease als dreistelliger Releaselinie und
# Zwischenrelease von 100 bis 999. Dieselbe Regel gilt für Tag und Bereitstellungsbranch.
_LIEFERSTAND_PATTERN = r"(?P<releaselinie>[0-9]{3})\.(?P<zwischenrelease>[1-9][0-9]{2})"

# Prüft einen Liefer-Tag wie `r260.108`. `.100` bezeichnet das Hauptrelease
# und ist die FULL-Basis für die späteren Zwischenreleases.
LIEFER_TAG_RE = re.compile("r" + _LIEFERSTAND_PATTERN)

# Prüft einen geschützten Branch einer gepflegten Releaselinie und erfasst die
# Releaselinie für die Auswahl des M/Text-Ziels.
_RELEASE_BRANCH_RE = re.compile(r"release/([0-9]{3})")

# Prüft einen Feature-Branch einschließlich hierarchischer Bezeichnung und
# erfasst die Releaselinie für die Entwicklungssynchronisation.
_FEATURE_BRANCH_RE = re.compile(r"feature/([0-9]{3})/(.+)")

# Prüft den temporären Arbeitsbranch einer Teillieferung und erfasst
# Releaselinie sowie Zwischenrelease, zum Beispiel `bereitstellung/261.108`.
BEREITSTELLUNG_BRANCH_RE = re.compile("bereitstellung/" + _LIEFERSTAND_PATTERN)


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von `git diff` gemeldete Änderung an einem Repositorypfad."""

    # Status aus `git diff --name-status`: A, M, D oder T
    status: str
    # Betroffener Repositorypfad
    path: str


def execute(repository: Path, *arguments: str, returncodes: tuple[int, ...] = (0,)) -> bytes:
    """Führt einen Git-Befehl aus und gibt seine Standardausgabe zurück.

    Bei einem unerwarteten Rückgabecode wird der Schritt mit `SOURCE_FAILED`
    beendet.
    """

    result = subprocess.run(
        ["git", "-C", repository.as_posix(), *arguments],  # -C: Befehl im Repository ausführen
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode not in returncodes:
        detail = result.stderr.decode(errors="replace").strip()
        message = f"Git-Operation fehlgeschlagen: {detail}" if detail else "Git-Operation fehlgeschlagen"
        raise DeliveryError(Status.SOURCE_FAILED, message)

    return result.stdout


def resolve(repository: Path, reference: str) -> str:
    """Löst eine bekannte Referenz in eine Commit-SHA auf."""

    # `^{commit}` löst die Referenz bis zum Commit auf und lehnt Tree- und Blob-Objekte ab.
    output = execute(
        repository,
        "rev-parse",
        "--verify",  # fehlende Referenzen als Fehler melden
        "--end-of-options",  # Referenz nicht als Option lesen
        f"{reference}^{{commit}}",
    )
    return output.decode("ascii").strip()


def reference_exists(repository: Path, reference: str) -> bool:
    """Prüft, ob eine vollständige Git-Referenz vorhanden ist."""

    output = execute(
        repository,
        "show-ref",
        "--verify",  # nur die angegebene vollständige Referenz prüfen
        reference,
        returncodes=(0, 128),  # 128: Referenz fehlt
    )
    return bool(output)


def require_ancestor(repository: Path, ancestor: str, descendant: str) -> None:
    """Fordert, dass ein Commit oder eine Referenz von einer anderen Referenz erreichbar ist.

    Damit lässt sich prüfen, ob ein Commit zum erwarteten Remote-Branch gehört
    oder ob ein Basistag vor dem Release-Tag liegt.
    """

    # `--is-ancestor` liefert Exit 0 nur bei echter Abstammung.
    execute(
        repository,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
    )


def resolve_sync_branch(source_branch: str, main_releaselinie: str) -> tuple[str, str]:
    """Ordnet einen zulässigen Quellbranch Releaselinie und M/Text-Zielstufe zu.

    `main` und `release/nnn` führen zum M/Text-Ziel Funktionstest,
    `feature/nnn/<Bezeichnung>` zum M/Text-Ziel Entwicklung. Weitere
    Schrägstriche in der Feature-Bezeichnung sind erlaubt.
    """

    # `main` führt die in der Mandantenkonfiguration hinterlegte Releaselinie.
    if source_branch == "main":
        return main_releaselinie, MTEXT_ZIEL_FUNKTIONSTEST

    release_match = _RELEASE_BRANCH_RE.fullmatch(source_branch)
    if release_match is not None:
        return release_match.group(1), MTEXT_ZIEL_FUNKTIONSTEST

    feature_match = _FEATURE_BRANCH_RE.fullmatch(source_branch)
    if feature_match is not None:
        return feature_match.group(1), MTEXT_ZIEL_ENTWICKLUNG

    raise DeliveryError(Status.VALIDATION_FAILED, "Branch ist kein Synchronisationszweig")


def changes(repository: Path, base: str, target: str) -> list[GitChange]:
    """Gibt Status und Pfade der Änderungen zwischen zwei Commits zurück.

    Die nullgetrennte Ausgabe erhält gültige Git-Pfade ohne Mehrdeutigkeit durch
    Quotierung. Git gibt Umbenennungen als Löschung und Hinzufügung aus, weil
    DELTA-Pakete und serverSync genau diese Dateioperationen benötigen.
    """

    # `--no-renames` liefert Umbenennungen als Löschung und Hinzufügung,
    # so wie DELTA-Pakete und die Synchronisation sie benötigen.
    output = execute(
        repository,
        "diff",
        "--name-status",  # Statusbuchstabe und Pfad je Änderung
        "-z",  # NUL-Trennung statt Quotierung der Pfade
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
