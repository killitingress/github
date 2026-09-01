"""Prüft JSON, XML und bei verfügbarem Node.js auch JavaScript.

Bei Pull Requests werden die geänderten Ressourcen geprüft. Ein manueller Lauf
prüft den gesamten Mandantenstand. Syntaxbefunde lassen den Lauf erfolgreich
enden und erscheinen als GitHub-Warnungen.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ElementTree
from fnmatch import fnmatchcase
from pathlib import Path

from . import git
from .config import RESOURCE_FORMATS_PATH, mandant_source
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


# Der beim Start gefundene Node.js-Befehl aktiviert die optionale JavaScript-Prüfung.
_NODE_COMMAND = shutil.which("node")


def _check_javascript(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine JavaScript-Datei mit Node.js und lokalisiert Syntaxfehler."""

    # Node.js nur parsen lassen, ohne das Skript auszuführen
    result = subprocess.run(
        [_NODE_COMMAND, "--check", str(path)],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return None

    # Zeile und eigentliche Syntaxmeldung aus der Node.js-Ausgabe übernehmen
    lines = result.stderr.splitlines()
    line_value = lines[0].rpartition(":")[2] if lines else ""
    line = int(line_value) if line_value.isdigit() else 1
    message = next(
        (e.removeprefix("SyntaxError: ") for e in lines if e.startswith("SyntaxError: ")),
        "JavaScript-Syntaxfehler",
    )
    return line, 1, message


# Die Formatzuordnung wählt über diese Tabelle den passenden Parser aus.
_CHECKERS = {"js": _check_javascript, "json": _check_json, "xml": _check_xml}


def _load_resource_formats(path: Path) -> dict[str, str]:
    """Lädt die gemeinsame Zuordnung von Endungsmustern zu technischen Formaten."""

    # konfigurierte Dateiendungen normalisieren und genau einem Parser zuordnen
    extensions = json.loads(path.read_text(encoding="utf-8"))["dateiendungen"]
    resource_formats: dict[str, str] = {}
    for extension, resource_format in extensions.items():
        normalized = extension.lower()
        if normalized in resource_formats:
            raise ValueError("Ressourcenformat-Zuordnung enthält ein Endungsmuster mehrfach")

        if resource_format not in _CHECKERS:
            raise ValueError("Ressourcenformat-Zuordnung ist ungültig")

        # JavaScript ohne verfügbares Node.js aus dem tatsächlichen Prüfumfang nehmen
        if resource_format == "js" and _NODE_COMMAND is None:
            continue

        resource_formats[normalized] = resource_format
    return resource_formats


def _resource_format(path: Path, resource_formats: dict[str, str]) -> str | None:
    """Ordnet die Dateiendung über die konfigurierten Muster einem Parser zu."""

    suffix = path.suffix.lower()
    for pattern, resource_format in resource_formats.items():
        if fnmatchcase(suffix, pattern):
            return resource_format
    return None


def _resource_paths(root: Path, resource_formats: dict[str, str], *, changed_only: bool) -> list[tuple[Path, str]]:
    """Ermittelt Ressourcendateien mit ihrem zugeordneten Parser."""

    # Kandidaten aus dem Pull-Request-Diff oder dem vollständigen Arbeitsbaum sammeln
    if changed_only:
        # Löschungen aus dem gemeinsamen Git-Diff fehlen im Arbeitsbaum und
        # werden durch is_file vor der Prüfung ausgeschlossen.
        candidates = [root / e.path for e in git.changes(root, "HEAD^1", "HEAD")]
    else:
        # manueller Lauf prüft den gesamten Mandantenstand ohne versteckte Verzeichnisse
        candidates = []
        for directory, directories, filenames in os.walk(root):
            directories[:] = [e for e in directories if not e.startswith(".")]
            candidates.extend(Path(directory) / e for e in filenames)

    # vorhandene reguläre Dateien außerhalb versteckter Pfade einem Parser zuordnen
    resources: list[tuple[Path, str]] = []
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue

        if any(e.startswith(".") for e in path.relative_to(root).parts):
            continue

        resource_format = _resource_format(path, resource_formats)
        if resource_format is not None:
            resources.append((path, resource_format))

    return sorted(resources, key=lambda item: item[0])


def _escape_workflow_command(value: object, *, property_value: bool = False) -> str:
    """Maskiert Zeichen, die GitHub als Teil eines Workflow-Kommandos liest."""

    escaped = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return escaped.replace(":", "%3A").replace(",", "%2C") if property_value else escaped


def run() -> dict[str, object]:
    """Prüft Ressourcen, schreibt Warnungen und gibt das Workflow-Ergebnis zurück."""

    # Prüfumfang aus dem Workflow-Ereignis bestimmen
    root = mandant_source().resolve()
    changed_only = os.environ["GITHUB_EVENT_NAME"] == "pull_request"

    # gemeinsame Formatzuordnung als technische Prüfgrenze laden
    try:
        resource_formats = _load_resource_formats(RESOURCE_FORMATS_PATH)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise DeliveryError(
            Status.VALIDATION_FAILED,
            f"Ressourcenformate können nicht geladen werden: {exc}",
        ) from exc

    # ausgewählte Ressourcen prüfen und Befunde mit Repositorypfad sammeln
    resources = _resource_paths(root, resource_formats, changed_only=changed_only)
    findings: list[tuple[Path, int, int, str]] = []
    for path, resource_format in resources:
        if (finding := _CHECKERS[resource_format](path)) is not None:
            findings.append((path.relative_to(root), *finding))

    # Syntaxbefunde als GitHub-Warnungen ausgeben, ohne den Lauf zu blockieren
    for path, line, column, message in findings:
        print(
            f"::warning file={_escape_workflow_command(path.as_posix(), property_value=True)},line={line},col={column},"
            f"title=Ungültige Ressource::{_escape_workflow_command(message)}"
        )

    # Anzahl und verfügbare Parser für die Workflow-Zusammenfassung festhalten
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary_path).write_text(
            (
                "## Prüfung der Ressourcen\n\n"
                f"- Geprüfte Dateien: {len(resources)}\n"
                f"- Warnungen: {len(findings)}\n"
                f"- JavaScript-Prüfung: {'aktiv' if _NODE_COMMAND else 'übersprungen, Node.js nicht verfügbar'}\n\n"
                "Syntaxbefunde werden als Warnungen angezeigt und blockieren den Pull Request nicht.\n"
            ),
            encoding="utf-8",
        )

    # erfolgreicher Prüflauf meldet Befunde als Anzahl, nicht als Fehlerstatus
    return {"status": Status.RESOURCE_CHECKED.value, "files": len(resources), "warnings": len(findings)}
