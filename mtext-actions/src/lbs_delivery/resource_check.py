"""Prüft Tonic-Ressourcen und config.json des Mandanten-Repositories."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ElementTree
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

from .config import FILETYPE_MAPPINGS_PATH, Configuration, mandant_source
from .process import Status
from .project_packages import Scope


# falls es das node Kommando gibt, wird auch eine Prüfung von JavaScript-Dateien ermöglicht
_NODE_COMMAND = shutil.which("node")


def _check_json(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine JSON-Datei auf Wohlgeformtheit und lokalisiert Syntaxfehler."""

    try:
        with path.open("rb") as source:
            json.load(source)
    except json.JSONDecodeError as error:
        return error.lineno, error.colno, error.msg

    return None


def _check_xml(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine XML-Datei auf Wohlgeformtheit und lokalisiert Parsefehler."""

    try:
        ElementTree.parse(path)
    except ElementTree.ParseError as error:
        line, column = error.position
        return line, column + 1, str(error)

    return None


def _check_javascript(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine JavaScript-Datei mit Node.js und lokalisiert Syntaxfehler."""

    result = subprocess.run(
        [_NODE_COMMAND, "--check", str(path)], # Syntax-Prüfung mittels --check
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )

    # wenn die Datei syntaktisch korrekt ist, gibt Node.js 0 zurück
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


def _load_filetype_mappings() -> dict[str, str]:
    """Lädt das Mapping von Dateiendungen zu technischen Formaten."""

    # Dateiendungen normalisieren und einem Parser zuordnen
    filetype_mappings: dict[str, str] = {}
    extensions = json.loads(FILETYPE_MAPPINGS_PATH.read_text(encoding="utf-8"))["dateiendungen"]

    for extension, filetype in extensions.items():
        if filetype not in ("js", "json", "xml"):
            raise ValueError(f"Dateitypen-Zuordnung ist ungültig: {filetype}")

        # JavaScript wird nur geprüft, wenn Node.js verfügbar ist
        if filetype == "js" and _NODE_COMMAND is None:
            continue

        filetype_mappings[extension.lower()] = filetype

    return filetype_mappings


def _relevant_resources(
    root: Path,
    mappings: dict[str, str],
    configuration: Configuration,
    scope: Scope | None,
) -> list[tuple[Path, str]]:
    """Ermittelt die Ressourcen des Prüfungsumfangs und ihre Parser."""

    # DELTA verwendet geänderte Pfade, FULL den sichtbaren Arbeitsbaum
    if scope is not None and scope.von is not None:
        candidates = [
            root / e.path
            for e in scope.changes
            if not any(part.startswith(".") for part in Path(e.path).parts)
        ]
    else:
        candidates: list[Path] = []
        for directory, directories, filenames in os.walk(root):
            directories[:] = [e for e in directories if not e.startswith(".")] # [:] ändert die von os.walk weiterverwendete Liste
            candidates.extend((Path(directory) / e) for e in filenames if not e.startswith("."))

    # Dateien aus ausgeschlossenen Projekten und ohne konfigurierten Parser überspringen
    result: list[tuple[Path, str]] = [] # Tupel aus Pfad und Dateityp
    for path in candidates:
        relative_path = path.relative_to(root)

        # ausgeschlossene Projekte und ungültige Elemente (z.B. gelöschte Dateien oder Symlinks) überspringen
        if configuration.excludes_project_path(relative_path) or (not path.is_file() or path.is_symlink()):
            continue

        # feststellen ob die Dateiendung zu einem konfigurierten Dateityp passt
        for pattern, filetype in mappings.items():
            if fnmatch(path.suffix.lower(), pattern):
                result.append((path, filetype))
                break

    return sorted(result)


def run(scope: Scope | None = None) -> dict[str, object]:
    """Prüft die Ressourcen des übergebenen FULL- oder DELTA-Umfangs."""

    root = mandant_source().resolve()
    configuration = Configuration.load(root, os.environ["GITHUB_REPOSITORY"])

    # Prüf-Funktionen je Dateityp
    checkers = {"json": _check_json, "xml": _check_xml, "js": _check_javascript}

    # Dateiendungs-Zuordnungen laden
    filetype_mappings = _load_filetype_mappings()

    # relevante Ressourcen ermitteln
    resources = _relevant_resources(root, filetype_mappings, configuration, scope)
    filetype_counts = Counter(e[1] for e in resources) # Anzahl der Ressourcen je Dateityp
    finding_counts: Counter[str] = Counter()
    findings: list[tuple[Path, int, int, str]] = []

    # Befunde sammeln
    for path, filetype in resources:
        if (finding := checkers[filetype](path)) is not None:
            findings.append((path.relative_to(root), *finding))
            finding_counts[filetype] += 1

    # Syntaxbefunde auf STDOUT ausgeben - mittels dem ::warning Kommando werden
    # daraus auch Annotations in der Job-Zusammenfassung. % und Zeilenumbrüche
    # ersetzen wir, um das Kommando nicht zu zerlegen.
    for path, line, column, message in findings:
        print(
            f"::warning file={path.as_posix()},line={line},col={column},"
            f"title=Ungültige Ressource::{message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')}"
        )

    # Workflow-Zusammenfassung erstellen
    summary = (
        "## Ressourcen-Prüfung\n\n"
        "| Dateityp | Geprüft | Befunde |\n"
        "| --- | ---: | ---: |\n"
        f"| JSON | {filetype_counts['json']} | {finding_counts['json']} |\n"
        f"| XML  | {filetype_counts['xml']} | {finding_counts['xml']} |\n"
        f"| JS   | {filetype_counts['js']} | {finding_counts['js']} |\n"
        f"| **Gesamt** | **{len(resources)}** | **{len(findings)}** |\n"
    )

    # erfolgreicher Prüflauf meldet Befunde als Anzahl, nicht als Fehlerstatus
    return {
        "status": Status.RESOURCE_CHECKED,
        "files": len(resources),
        "warnings": len(findings),
        "summary": summary,
    }
