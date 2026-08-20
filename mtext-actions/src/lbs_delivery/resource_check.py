"""Prüft konfigurierte JSON- und XML-Ressourcen und meldet Warnungen.

Bei Pull Requests werden die geänderten Ressourcen geprüft. Ein manueller Lauf
prüft den gesamten Mandantenstand. Syntaxbefunde lassen den Lauf erfolgreich
enden und erscheinen als GitHub-Warnungen.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from . import git
from .process import DeliveryError, Status


def _check_json(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine JSON-Datei und lokalisiert Syntaxfehler."""

    try:
        with path.open("rb") as source:
            json.load(source)
    except json.JSONDecodeError as error:
        return error.lineno, error.colno, error.msg
    except UnicodeError as error:
        return 1, 1, str(error)
    return None


def _check_xml(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine XML-Datei auf Wohlgeformtheit und lokalisiert Parsefehler."""

    try:
        ElementTree.parse(path)
    except ElementTree.ParseError as error:
        line, column = error.position
        return line, column + 1, str(error)
    except UnicodeError as error:
        return 1, 1, str(error)
    return None


# Die Formatzuordnung wählt über diese Tabelle den passenden Parser aus.
_CHECKERS = {"json": _check_json, "xml": _check_xml}


def _load_resource_formats(path: Path) -> dict[str, str]:
    """Lädt die zentrale Zuordnung von Dateiendungen zu technischen Formaten."""

    extensions = json.loads(path.read_text(encoding="utf-8"))["dateiendungen"]
    resource_formats: dict[str, str] = {}
    for extension, resource_format in extensions.items():
        # Endungen werden kleingeschrieben und müssen eindeutig einem bekannten Parser gehören.
        normalized = extension.lower()
        if normalized in resource_formats:
            raise ValueError("Ressourcenformat-Zuordnung enthält eine Dateiendung mehrfach")
        if resource_format not in _CHECKERS:
            raise ValueError("Ressourcenformat-Zuordnung ist ungültig")
        resource_formats[normalized] = resource_format
    return resource_formats


def _resource_paths(root: Path, resource_formats: dict[str, str], *, changed_only: bool) -> list[Path]:
    """Ermittelt alle oder die im Pull Request geänderten Ressourcendateien."""

    if changed_only:
        # Löschungen aus dem gemeinsamen Git-Diff fehlen im Arbeitsbaum und
        # werden durch is_file vor der Prüfung ausgeschlossen.
        candidates = [root / change.path for change in git.changes(root, "HEAD^1", "HEAD")]
    else:
        # Manueller Lauf prüft den gesamten Mandantenstand ohne versteckte Verzeichnisse.
        candidates = []
        for directory, directories, filenames in os.walk(root):
            directories[:] = [name for name in directories if not name.startswith(".")]
            candidates.extend(Path(directory) / filename for filename in filenames)

    # Nur vorhandene Dateien mit bekannter Endung außerhalb versteckter Pfade prüfen.
    return sorted(
        path
        for path in candidates
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in resource_formats
            and not any(part.startswith(".") for part in path.relative_to(root).parts)
        )
    )


def _escape_workflow_command(value: object, *, property_value: bool = False) -> str:
    """Maskiert Zeichen, die GitHub als Teil eines Workflow-Kommandos liest."""

    escaped = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return escaped.replace(":", "%3A").replace(",", "%2C") if property_value else escaped


def run(*, root: Path, formats_path: Path, changed_only: bool) -> dict[str, object]:
    """Prüft Ressourcen, schreibt Warnungen und gibt das Workflow-Ergebnis zurück."""

    # Formatzuordnung laden und die ausgewählten Ressourcen prüfen.
    try:
        resource_formats = _load_resource_formats(formats_path)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise DeliveryError(Status.VALIDATION_FAILED, str(exc)) from exc

    paths = _resource_paths(root, resource_formats, changed_only=changed_only)
    findings: list[tuple[Path, int, int, str]] = []
    for path in paths:
        # Der Parser richtet sich nach der Endung aus der Formatzuordnung.
        if (finding := _CHECKERS[resource_formats[path.suffix.lower()]](path)) is not None:
            findings.append((path.relative_to(root), *finding))

    # Syntaxbefunde als GitHub-Warnungen ausgeben, ohne den Lauf zu blockieren.
    for path, line, column, message in findings:
        print(
            f"::warning file={_escape_workflow_command(path.as_posix(), property_value=True)},line={line},col={column},"
            f"title=Ungültige Ressource::{_escape_workflow_command(message)}"
        )

    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary_path).write_text(
            (
                "## Prüfung der JSON- und XML-Ressourcen\n\n"
                f"- Geprüfte Dateien: {len(paths)}\n"
                f"- Warnungen: {len(findings)}\n\n"
                "Syntaxbefunde werden als Warnungen angezeigt und blockieren den Pull Request nicht.\n"
            ),
            encoding="utf-8",
        )

    return {"status": Status.RESOURCE_CHECKED.value, "files": len(paths), "warnings": len(findings)}
