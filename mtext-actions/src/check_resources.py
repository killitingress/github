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


# Die Formatzuordnung wählt über diese Tabelle den passenden Parser aus.
CHECKERS = {"json": check_json, "xml": check_xml}


def load_resource_formats(path: Path) -> dict[str, str]:
    """Lädt die zentrale Zuordnung von Dateiendungen zu technischen Formaten."""

    extensions = json.loads(path.read_text(encoding="utf-8"))["dateiendungen"]
    resource_formats: dict[str, str] = {}

    # Endungen werden einmal vereinheitlicht.
    for extension, resource_format in extensions.items():
        normalized = extension.lower()
        if normalized in resource_formats:
            raise ValueError("Ressourcenformat-Zuordnung enthält eine Dateiendung mehrfach")
        if resource_format not in CHECKERS:
            raise ValueError("Ressourcenformat-Zuordnung ist ungültig")
        resource_formats[normalized] = resource_format
    return resource_formats


def resource_paths(root: Path, resource_formats: dict[str, str], *, changed_only: bool = False) -> list[Path]:
    """Ermittelt alle oder die im Pull Request geänderten Ressourcendateien."""

    if changed_only:
        # Im Pull-Request-Workflow liefert GitHub einen Merge-Commit: HEAD^1 ist der
        # Zielbranch, HEAD der zusammengeführte PR-Stand. Der Diff listet nur Änderungen dieses PRs.
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", "-z", "--diff-filter=ACMRT", "HEAD^1", "HEAD", "--"],
                check=True,
                capture_output=True,
            )
        except OSError as error:
            raise RuntimeError("Git ist für die Ermittlung geänderter Ressourcen nicht verfügbar") from error
        except subprocess.CalledProcessError as error:
            detail = os.fsdecode(error.stderr).strip()
            raise RuntimeError(f"Geänderte Ressourcen können nicht ermittelt werden: {detail}") from None
        candidates = [root / os.fsdecode(relative_path) for relative_path in result.stdout.split(b"\0") if relative_path]
    else:
        candidates = []

        # Ein manueller Lauf durchsucht den Repositorybaum. Versteckte
        # Verwaltungsverzeichnisse wie `.git` und `.github` gehören nicht zu den
        # M/Text-Ressourcen und werden schon beim Durchlaufen ausgelassen.
        for directory, directories, filenames in os.walk(root):
            directories[:] = [name for name in directories if not name.startswith(".")]
            candidates.extend(Path(directory) / filename for filename in filenames)

    # Geprüft werden vorhandene reguläre Dateien mit einer konfigurierten Endung.
    # Symlinks und versteckte Pfade gelten nicht als M/Text-Ressourcen.
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


def check_resources(root: Path, resource_formats: dict[str, str], *, changed_only: bool = False) -> tuple[list[Path], list[tuple[Path, int, int, str]]]:
    """Prüft die ausgewählten Ressourcen und gibt Dateien sowie Befunde zurück."""

    paths = resource_paths(root, resource_formats, changed_only=changed_only)
    findings: list[tuple[Path, int, int, str]] = []

    # Die Dateiendung bestimmt den Parser. Befunde werden zunächst gesammelt,
    # damit Protokoll, Laufübersicht und JSON-Ergebnis dieselben Zahlen verwenden.
    for path in paths:
        if (finding := CHECKERS[resource_formats[path.suffix.lower()]](path)) is not None:
            findings.append((path.relative_to(root), *finding))
    return paths, findings


def write_warning(path: Path, line: int, column: int, message: str) -> None:
    """Schreibt einen Befund als Datei-Warnung in das GitHub-Actions-Protokoll."""

    def escape(value: object, *, property_value: bool = False) -> str:
        """Maskiert Zeichen, die GitHub als Teil eines Workflow-Kommandos liest."""

        escaped = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return escaped.replace(":", "%3A").replace(",", "%2C") if property_value else escaped

    print(
        f"::warning file={escape(path.as_posix(), property_value=True)},line={line},col={column},"
        f"title=Ungültige Ressource::{escape(message)}"
    )


def build_parser() -> argparse.ArgumentParser:
    """Definiert das zu prüfende Repositoryverzeichnis für den Workflow-Aufruf."""

    parser = argparse.ArgumentParser(prog="check-resources")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--formats", type=Path, required=True)
    parser.add_argument("--changed-only", action="store_true", help="nur im Pull-Request-Merge geänderte Ressourcen prüfen")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Prüft den Repositorybaum und meldet Befunde ohne den Lauf zu blockieren."""

    arguments = build_parser().parse_args(argv)
    root = arguments.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Repositoryverzeichnis fehlt: {root}")

    # Zuerst wird festgelegt, welche Endungen mit welchem Parser geprüft werden.
    # Danach wählt der Auslöser entweder die PR-Änderungen oder den ganzen Baum.
    try:
        paths, findings = check_resources(root, load_resource_formats(arguments.formats), changed_only=arguments.changed_only)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit("Ressourcenformat-Zuordnung ist ungültig") from error

    # Syntaxbefunde erscheinen als Annotationen, beenden den Lauf aber nicht.
    for path, line, column, message in findings:
        write_warning(path, line, column, message)

    # GitHub stellt den Pfad nur innerhalb eines Actions-Laufs bereit. Bei einem
    # lokalen Aufruf genügt deshalb die abschließende JSON-Ausgabe.
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

    print(json.dumps({"status": "RESOURCE_CHECKED", "files": len(paths), "warnings": len(findings)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
