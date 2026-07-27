"""Bereitet abgestimmte Workflow-Aktualisierungen für Automation und Mandanten-Repositories vor.

Das Werkzeug setzt die Runner-Kennzeichen in den zentralen Workflows, bindet die
Mandanten-Workflows an den entstandenen Commit und erstellt die Rollout-Matrix
für alle aktiven Releaselinienbranches.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from lbs_delivery.config import (
    AUTOMATION_ROOT,
    load_mandanten_zuordnung,
    load_releaselinien_zuordnung,
)
from lbs_delivery.process import DeliveryError


# Die von Mandanten-Repositories eingebundenen wiederverwendbaren Workflows werden hier gepflegt.
AUTOMATION_REPOSITORY = "j520730/mtext-actions"
# Dieses Kennzeichen markiert einen Runner, dessen betrieblicher Wert vor dem
# Rollout der zentralen Workflows noch festgelegt werden muss.
RUNNER_PLACEHOLDER = "FI_RUNNER_LABEL_TO_BE_SET"
# Der Aktualisierungsworkflow behält seinen konfigurierbaren Bootstrap-Runner und
# wird deshalb beim Einsetzen fester Runner-Kennzeichen ausgelassen.
UPDATE_WORKFLOW = "update-mandant-workflows.yml"
# Jede aktive Releaselinie wird über diese drei Branchstufen aktualisiert.
MANDANT_BRANCH_STUFEN = ("Entwicklung", "Abnahme", "Bereitstellung")

# Reguläre Ausdrücke finden die technischen Workflow-Felder dieses Werkzeugs.
# Erfasst ein skalares `runs-on`-Feld und erhält Einrückung sowie Schlüssel.
RUNS_ON_PATTERN = re.compile(r"(?m)^(\s*runs-on:\s*).+$")
# Erfasst die Revision eines wiederverwendbaren Workflows aus dem zentralen
# Automations-Repository und erhält Kommentare sowie umgebendes YAML.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)
# Erfasst den Wert `automation_ref` für den Checkout der Python-Implementierung
# und erhält Leerraum sowie einen möglichen nachgestellten YAML-Kommentar.
AUTOMATION_REF_PATTERN = re.compile(r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$")


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Führt eine erforderliche Git-Operation aus und gibt ihre Textausgabe zurück.

    Die Befehle umgehen eine Shell. Repositorypfade und erzeugte Revisionen
    können die Befehlsstruktur dadurch nicht verändern. Bei Fehlern bleibt die
    von Git gelieferte Diagnose erhalten.
    """

    try:
        return subprocess.run(["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True)
    except OSError as error:
        raise RuntimeError("Git ist für die Mandanten-Aktualisierung nicht verfügbar") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Git-Operation fehlgeschlagen: {detail}") from None


def _automation_changes(automation_root: Path, runner_label: str) -> dict[Path, str]:
    """Setzt das gewählte Runner-Kennzeichen in alle zentralen wiederverwendbaren Workflows ein.

    Die Funktion gibt die vorgesehenen Dateiinhalte zurück, ohne sie zu schreiben.
    Dieselbe Umformung kann dadurch für Aktualisierung und Abschlussprüfung
    verwendet werden.
    """

    workflow_paths = (automation_root / ".github/workflows").glob("*.yml")
    workflows = sorted(path for path in workflow_paths if path.name != UPDATE_WORKFLOW)
    if not workflows:
        raise ValueError("keine zentralen Workflows gefunden")

    changes: dict[Path, str] = {}
    for path in workflows:
        original = path.read_text(encoding="utf-8")
        rendered, replacements = RUNS_ON_PATTERN.subn(rf"\g<1>{json.dumps(runner_label)}", original)
        if replacements == 0:
            raise ValueError(f"kein runs-on-Feld in {path}")
        if rendered != original:
            changes[path] = rendered
    return changes


def _mandant_changes(mandant_root: Path, automation_sha: str) -> dict[Path, str]:
    """Setzt einen Automations-Commit in die Workflow-Referenzen eines Mandantenbranches ein.

    Verweise auf wiederverwendbare Workflows und Python-Checkouts müssen gleich
    häufig vorkommen. Ein Mandant kann dadurch Workflow-YAML und
    Implementierungscode nicht aus unterschiedlichen Revisionen ausführen.
    """

    workflows = sorted((mandant_root / ".github/workflows").glob("*.yml"))
    if not workflows:
        raise ValueError(f"keine Mandanten-Workflows unter {mandant_root} gefunden")

    changes: dict[Path, str] = {}
    for path in workflows:
        original = path.read_text(encoding="utf-8")
        workflow_references = list(CENTRAL_USES_PATTERN.finditer(original))
        code_references = list(AUTOMATION_REF_PATTERN.finditer(original))
        if not workflow_references or len(workflow_references) != len(code_references):
            raise ValueError(f"zentrale Workflowreferenzen fehlen in {path}")
        rendered = CENTRAL_USES_PATTERN.sub(rf"\g<1>{automation_sha}\g<3>", original)
        rendered = AUTOMATION_REF_PATTERN.sub(rf"\g<1>{automation_sha}\g<3>", rendered)
        if rendered != original:
            changes[path] = rendered
    return changes


def _commit(repository: Path, message: str) -> str:
    """Zeigt geänderte Workflow-Dateien, schreibt sie in einen Commit und gibt dessen SHA zurück.

    Auf den Workflow-Pfad begrenzte Status-, Diff- und Commit-Befehle halten
    andere Änderungen aus dem Rollout-Commit heraus. Ohne Workflow-Änderung wird
    der bestehende HEAD zurückgegeben.
    """

    changed = bool(_git(repository, "status", "--short", "--", ".github/workflows").stdout)
    if changed:
        _git(repository, "diff", "--check", "--", ".github/workflows")
        print(_git(repository, "diff", "--", ".github/workflows").stdout, file=sys.stderr)
        _git(repository, "commit", "--no-gpg-sign", "--only", "-m", message, "--", ".github/workflows")
    return _git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()


def prepare_automation_update(automation_root: Path, runner_label: str, automation_sha: str) -> str:
    """Finalisiert die zentralen Runner-Kennzeichen und gibt den Commit für die Mandantenbindung zurück.

    Die erwartete Checkout-SHA verhindert die Bearbeitung einer anderen zentralen
    Revision. Eine erneute Umformung nach dem Commit belegt, dass kein
    vorgesehener Platzhalter oder veraltetes Kennzeichen verblieben ist.
    """

    if not runner_label.strip() or "\n" in runner_label or runner_label == RUNNER_PLACEHOLDER:
        raise ValueError("Runner-Kennzeichen muss ein einzeiliger Wert der FI sein")
    checkout_sha = _git(automation_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if checkout_sha != automation_sha:
        raise ValueError("zentraler Checkout entspricht nicht dem angegebenen Commit")

    automation_changes = _automation_changes(automation_root, runner_label)
    for path, text in automation_changes.items():
        path.write_text(text, encoding="utf-8")
    automation_sha = _commit(automation_root, "Runner der FI in zentralen Workflows aktualisieren")
    if _automation_changes(automation_root, runner_label):
        raise RuntimeError("abschließende Prüfung der zentralen Workflows ist nicht leer")
    return automation_sha


def prepare_mandant_update(automation_root: Path, mandant_root: Path, rollout_sha: str) -> str:
    """Bindet einen Mandantenbranch an den geprüften zentralen Rollout-Commit.

    Vor Änderungen an Mandantendateien wird der Automations-Checkout geprüft.
    Eine zweite Umformung belegt anschließend, dass der Branchstand nach dem
    Commit einheitliche Workflow- und Codereferenzen enthält.
    """

    checkout_sha = _git(automation_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if checkout_sha != rollout_sha:
        raise ValueError("zentraler Checkout entspricht nicht der Rollout-SHA")

    mandant_changes = _mandant_changes(mandant_root, rollout_sha)
    for path, text in mandant_changes.items():
        path.write_text(text, encoding="utf-8")
    mandant_sha = _commit(mandant_root, "Zentrale Workflowversion aktualisieren [skip ci]")
    if _mandant_changes(mandant_root, rollout_sha):
        raise RuntimeError("abschließende Prüfung des Mandantenbranches ist nicht leer")
    return mandant_sha


def build_update_matrix(mandanten_path: Path, releaselinien_path: Path) -> dict[str, list[dict[str, str]]]:
    """Erstellt die Workflow-Matrix für alle Mandanten, Releaselinien und Branchstufen.

    Die zentralen Zuordnungen gleichen den Rollout mit demselben Repository- und
    Releaselinienbestand ab, den auch die Lieferprüfung verwendet.
    """

    mandanten = load_mandanten_zuordnung(mandanten_path)
    releaselinien = load_releaselinien_zuordnung(releaselinien_path)

    include = [
        {
            "repository": stammdaten.repository,
            "kuerzel": kuerzel,
            "branch": f"{releaselinie}/{stufe}",
        }
        for kuerzel, stammdaten in sorted(mandanten.items())
        for releaselinie in sorted(releaselinien)
        for stufe in MANDANT_BRANCH_STUFEN
    ]
    return {"include": include}


def build_parser() -> argparse.ArgumentParser:
    """Definiert die drei Kommandos des Workflow-Aktualisierungsprozesses.

    Jedes Unterkommando entspricht der Grenze eines Workflow-Jobs und nimmt die
    von diesem Job benötigten Werte entgegen.
    """

    parser = argparse.ArgumentParser(prog="workflow-configuration")
    commands = parser.add_subparsers(dest="command", required=True)

    automation = commands.add_parser("prepare-automation")
    automation.add_argument("--runner-label", required=True)
    automation.add_argument("--automation-sha", required=True)

    mandant = commands.add_parser("prepare-mandant")
    mandant.add_argument("--mandant-root", type=Path, required=True)
    mandant.add_argument("--rollout-sha", required=True)

    commands.add_parser("update-matrix")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt den ausgewählten Vorbereitungsschritt aus und gibt kompaktes JSON aus.

    Erwartete Konfigurations-, Datei- und Git-Fehler werden in einen
    Kommandozeilenfehler übersetzt. Erfolgreiche Ausgaben bleiben für
    Workflow-Schritte leicht verarbeitbar.
    """

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "prepare-automation":
            rollout_sha = prepare_automation_update(AUTOMATION_ROOT, arguments.runner_label, arguments.automation_sha)
            result = {"rollout_sha": rollout_sha}
        elif arguments.command == "prepare-mandant":
            result = {
                "mandant_sha": prepare_mandant_update(AUTOMATION_ROOT, arguments.mandant_root, arguments.rollout_sha)
            }
        elif arguments.command == "update-matrix":
            result = build_update_matrix(
                AUTOMATION_ROOT / "config/mandanten.json",
                AUTOMATION_ROOT / "config/releaselinien.json",
            )
        else:
            raise AssertionError(f"unbekanntes Kommando: {arguments.command}")
    except (DeliveryError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Mandanten-Aktualisierung kann nicht vorbereitet werden: {error}") from None
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
