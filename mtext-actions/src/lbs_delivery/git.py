"""Spricht das lokale Git-Repository für Synchronisierung und Lieferung an."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .process import DeliveryError, Status


_LIEFERSTAND_PATTERN = r"(?P<releaselinie>[0-9]{3})\.(?P<zwischenrelease>[1-9][0-9]{2})"
LIEFER_TAG_RE = re.compile("r" + _LIEFERSTAND_PATTERN)
BEREITSTELLUNG_BRANCH_RE = re.compile("bereitstellung/" + _LIEFERSTAND_PATTERN)
RELEASE_BRANCH_RE = re.compile(r"release/([0-9]{3})")


@dataclass(frozen=True, order=True)
class LieferTag:
    releaselinie: str
    zwischenrelease: str

    @classmethod
    def parse(cls, value: str) -> LieferTag:
        """Prüft einen Git-Namen und gibt seinen Lieferstand zurück."""

        match = LIEFER_TAG_RE.fullmatch(value)
        if match is None:
            raise ValueError(f"ungültiges Format des Liefer-Tags rnnn.nnn: {value}")

        return cls(match.group("releaselinie"), match.group("zwischenrelease"))

    @classmethod
    def from_bereitstellung(cls, branch: str) -> LieferTag | None:
        """Gibt den Lieferstand eines Bereitstellungsbranches zurück."""

        match = BEREITSTELLUNG_BRANCH_RE.fullmatch(branch)
        if match is None:
            return None

        return cls(match.group("releaselinie"), match.group("zwischenrelease"))

    @classmethod
    def from_lieferzweig(cls, branch: str, fuehrende_releaselinie: str) -> LieferTag | None:
        """Liest den Liefer-Tag, wenn der Branch eine Mainframe-Lieferung starten darf.

        Ein Bereitstellungsbranch wie `bereitstellung/261.108` ergibt `r261.108`.
        `main` ergibt das `.100` der führenden Releaselinie, bei `270` also `r270.100`.
        `release/261` ergibt `r261.100`. Andere Branches, etwa `feature/261/kunde`,
        liefern `None`.
        """

        if tag := cls.from_bereitstellung(branch):
            return tag

        if branch == "main":
            return cls(fuehrende_releaselinie, "100")

        if match := RELEASE_BRANCH_RE.fullmatch(branch):
            return cls(match.group(1), "100")

        return None

    @property
    def ist_hauptrelease(self) -> bool:
        return self.zwischenrelease == "100"

    def __str__(self) -> str:
        return f"r{self.releaselinie}.{self.zwischenrelease}"


@dataclass(frozen=True)
class GitChange:
    """Beschreibt eine von `git diff` gemeldete Änderung an einem Repositorypfad."""

    # Status aus `git diff --name-status`: A, M, D oder T
    status: str
    # Betroffener Repositorypfad
    path: str


def execute(repository: Path, *arguments: str, returncodes: tuple[int, ...] = (0,)) -> bytes:
    """Führt einen Git-Befehl aus und gibt seine Standardausgabe zurück.

    Ein fehlendes Git oder ein unerwarteter Rückgabecode beendet den Schritt
    mit `SOURCE_FAILED`.
    """

    try:
        result = subprocess.run(
            ["git", "-C", repository.as_posix(), *arguments],  # -C: Befehl im Repository ausführen
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise DeliveryError(Status.SOURCE_FAILED, f"Git-Operation fehlgeschlagen: {exc}") from exc

    if result.returncode not in returncodes:
        detail = result.stderr.decode(errors="replace").strip()
        message = f"Git-Operation fehlgeschlagen: {detail}" if detail else "Git-Operation fehlgeschlagen"
        raise DeliveryError(Status.SOURCE_FAILED, message)

    return result.stdout


def resolve(repository: Path, reference: str) -> str:
    """Gibt die Commit-SHA eines Git-Namens zurück, der im Repository vorkommen muss.

    `HEAD` ergibt den ausgecheckten Commit. `refs/tags/r261.108` ergibt den
    Commit des Liefer-Tags. Ein fehlender Name oder ein Objekt, das kein Commit
    ist, beendet den Schritt mit `SOURCE_FAILED`.
    """

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
    """Prüft, dass der Ausgangscommit vom Zielcommit aus erreichbar ist."""

    # Git akzeptiert auch identische Commits als unveränderten Vergleichsstand
    execute(
        repository,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
    )


def changes(repository: Path, base: str, target: str) -> list[GitChange]:
    """Status und Pfade der Änderungen zwischen zwei Commits via Git-Diff."""

    # `--no-renames` liefert Umbenennungen als Löschung und Hinzufügung,
    # so wie DELTA-Pakete und die Synchronisierung sie benötigen.
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
    return [GitChange(e[0], next(fields)) for e in fields]


def project_changes(git_changes: Iterable[GitChange], project: str) -> Iterator[tuple[str, str]]:
    """Gibt die Dateiänderungen eines Projekts zurück."""

    prefix = f"{project}/"
    for change in git_changes:
        if change.path == project or change.path.startswith(prefix):
            yield change.status, change.path
