"""Prüft konfigurierte JSON- und XML-Ressourcen und meldet Warnungen.

Der Einstieg wird im Pull-Request-Workflow eines Mandanten-Repositories
verwendet. Die Prüfung liest die geänderten Dateien oder bei einem manuellen
Start den gesamten Stand. Sie verändert keine Dateien und beendet den Lauf auch
bei Befunden erfolgreich.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path


def reject_nonstandard_number(value: str) -> None:
    """Lehnt JavaScript-Zahlen ab, die der JSON-Standard nicht erlaubt."""

    raise ValueError(f"nicht erlaubter Zahlenwert {value}")


def check_json(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine JSON-Datei nach dem JSON-Standard und lokalisiert Syntaxfehler."""

    try:
        with path.open("rb") as source:
            json.load(source, parse_constant=reject_nonstandard_number)
    except json.JSONDecodeError as error:
        return error.lineno, error.colno, error.msg
    except (UnicodeError, ValueError) as error:
        return 1, 1, str(error)
    return None


def check_xml(path: Path) -> tuple[int, int, str] | None:
    """Prüft eine XML-Datei auf Wohlgeformtheit und lokalisiert Parsefehler."""

    try:
        ElementTree.parse(path)
    except ElementTree.ParseError as error:
        line, column = error.position
        return line, column + 1, str(error)
    except UnicodeError as error:
        return 1, 1, str(error)
    return None


# Diese Zuordnung ist der ausführbare Vertrag der unterstützten technischen
# Formate. Die Konfigurationsprüfung weist alle anderen Formatwerte zurück.
CHECKERS = {
    "json": check_json,
    "xml": check_xml,
}


def load_resource_formats(path: Path) -> dict[str, str]:
    """Lädt die zentrale Zuordnung von Dateiendungen zu technischen Formaten."""

    try:
        configuration = json.loads(path.read_text(encoding="utf-8"))
        extensions = configuration["dateiendungen"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("Ressourcenformat-Zuordnung ist ungültig") from error
    if not isinstance(extensions, dict) or not extensions:
        raise ValueError("Ressourcenformat-Zuordnung ist ungültig")

    resource_formats: dict[str, str] = {}
    for extension, resource_format in extensions.items():
        if (
            not isinstance(extension, str)
            or not extension.startswith(".")
            or not isinstance(resource_format, str)
            or resource_format not in CHECKERS
        ):
            raise ValueError("Ressourcenformat-Zuordnung ist ungültig")
        normalized_extension = extension.lower()
        if normalized_extension in resource_formats:
            raise ValueError("Ressourcenformat-Zuordnung enthält eine Dateiendung mehrfach")
        resource_formats[normalized_extension] = resource_format
    return resource_formats


def resource_paths(
    root: Path, resource_formats: dict[str, str], *, changed_only: bool = False,
) -> list[Path]:
    """Ermittelt alle oder die im Pull Request geänderten Prüfgegenstände."""

    if changed_only:
        # Der Pull-Request-Checkout ist ein Merge-Commit. Sein erster Elternteil
        # ist der Zielbranch, sodass der Vergleich den vorgeschlagenen Inhalt
        # unabhängig von älteren Änderungen des Feature-Branches abgrenzt.
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "diff",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACMRT",
                    "HEAD^1",
                    "HEAD",
                    "--",
                ],
                check=True,
                capture_output=True,
            )
        except OSError as error:
            raise RuntimeError("Git ist für die Ermittlung geänderter Ressourcen nicht verfügbar") from error
        except subprocess.CalledProcessError as error:
            detail = os.fsdecode(error.stderr).strip()
            raise RuntimeError(f"Geänderte Ressourcen können nicht ermittelt werden: {detail}") from None

        candidates = [
            root / os.fsdecode(relative_path)
            for relative_path in result.stdout.split(b"\0")
            if relative_path
        ]
    else:
        candidates = []
        # Versteckte Verwaltungsverzeichnisse wie `.git` und `.github` gehören
        # nicht zu den M/Text-Ressourcen und werden bei einer Vollprüfung nicht
        # durchlaufen.
        for directory, directories, filenames in os.walk(root):
            directories[:] = [name for name in directories if not name.startswith(".")]
            candidates.extend(Path(directory) / filename for filename in filenames)

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


def check_resources(
    root: Path, resource_formats: dict[str, str], *, changed_only: bool = False,
) -> tuple[list[Path], list[tuple[Path, int, int, str]]]:
    """Prüft die ausgewählten Ressourcen und gibt Dateien sowie Befunde zurück."""

    paths = resource_paths(root, resource_formats, changed_only=changed_only)
    findings: list[tuple[Path, int, int, str]] = []
    for path in paths:
        resource_format = resource_formats[path.suffix.lower()]
        finding = CHECKERS[resource_format](path)
        if finding is not None:
            line, column, message = finding
            findings.append((path.relative_to(root), line, column, message))
    return paths, findings


def workflow_escape(value: object, *, property_value: bool = False) -> str:
    """Maskiert fremde Dateiinhalte für eine sichere GitHub-Workflow-Ausgabe."""

    escaped = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        escaped = escaped.replace(":", "%3A").replace(",", "%2C")
    return escaped


def write_warning(path: Path, line: int, column: int, message: str) -> None:
    """Schreibt einen Befund als Datei-Warnung in das GitHub-Actions-Protokoll."""

    relative_path = workflow_escape(path.as_posix(), property_value=True)
    warning = workflow_escape(message)
    print(
        f"::warning file={relative_path},line={line},col={column},title=Ungültige Ressource::{warning}"
    )


def write_summary(path: Path, checked_files: int, warning_count: int) -> None:
    """Schreibt das kompakte Prüfergebnis auf die GitHub-Laufübersicht."""

    path.write_text(
        (
            "## Prüfung der JSON- und XML-Ressourcen\n\n"
            f"- Geprüfte Dateien: {checked_files}\n"
            f"- Warnungen: {warning_count}\n\n"
            "Syntaxbefunde werden als Warnungen angezeigt und blockieren den Pull Request nicht.\n"
        ),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    """Definiert das zu prüfende Repositoryverzeichnis für den Workflow-Aufruf."""

    parser = argparse.ArgumentParser(prog="check-resources")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--formats", type=Path, required=True)
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="nur im Pull-Request-Merge geänderte Ressourcen prüfen",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Prüft den Repositorybaum und meldet Befunde ohne den Lauf zu blockieren."""

    arguments = build_parser().parse_args(argv)
    root = arguments.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Repositoryverzeichnis fehlt: {root}")

    try:
        resource_formats = load_resource_formats(arguments.formats)
        paths, findings = check_resources(
            root,
            resource_formats,
            changed_only=arguments.changed_only,
        )
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    for path, line, column, message in findings:
        write_warning(path, line, column, message)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        write_summary(Path(summary_path), len(paths), len(findings))

    print(
        json.dumps(
            {
                "status": "RESOURCE_CHECKED",
                "files": len(paths),
                "warnings": len(findings),
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
