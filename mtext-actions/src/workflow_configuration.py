"""Bereitet den zentralen Stand und die Mandanten-Aktualisierungen vor."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from lbs_delivery.config import (
    load_mandanten_zuordnung,
    load_releaselinien_zuordnung,
)
from lbs_delivery.errors import DeliveryError


# Dieses Repository ist die freigegebene Quelle der wiederverwendbaren Workflows.
AUTOMATION_REPOSITORY = "j520730/mtext-actions"
# Dieses Kennzeichen markiert die noch ausstehende Festlegung des Runners der FI.
RUNNER_PLACEHOLDER = "FI_RUNNER_LABEL_TO_BE_SET"
# Der Aktualisierungsworkflow benötigt zur Bootstrap-Zeit einen variablen Runner.
UPDATE_WORKFLOW = "update-mandant-workflows.yml"
# Diese Branchstufen werden für jede aktive Releaselinie aktualisiert.
MANDANT_BRANCH_STUFEN = ("Entwicklung", "Abnahme", "Bereitstellung")

# Reguläre Ausdrücke erkennen die verbindlichen technischen Workflowfelder.
# Erfasst den skalaren runs-on-Wert eines zentralen Jobs.
RUNS_ON_PATTERN = re.compile(r"(?m)^(\s*runs-on:\s*).+$")
# Erfasst den Versionsanteil eines zentralen Workflowaufrufs.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)
# Erfasst den Checkout-Pin der zentralen Python-Implementierung.
AUTOMATION_REF_PATTERN = re.compile(
    r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$"
)


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Führt eine erforderliche Git-Operation ohne Shell aus."""

    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError(
            "Git ist für die Mandanten-Aktualisierung nicht verfügbar"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Git-Operation fehlgeschlagen: {detail}") from None


def _automation_changes(automation_root: Path, runner_label: str) -> dict[Path, str]:
    """Ermittelt die festen Runnerwerte der zentralen Fach- und Testworkflows."""

    workflows = sorted(
        path
        for path in (automation_root / ".github/workflows").glob("*.yml")
        if path.name != UPDATE_WORKFLOW
    )
    if not workflows:
        raise ValueError("keine zentralen Workflows gefunden")

    changes: dict[Path, str] = {}
    for path in workflows:
        original = path.read_text(encoding="utf-8")
        rendered, replacements = RUNS_ON_PATTERN.subn(
            rf"\g<1>{json.dumps(runner_label)}", original
        )
        if replacements == 0:
            raise ValueError(f"kein runs-on-Feld in {path}")
        if rendered != original:
            changes[path] = rendered
    return changes


def _mandant_changes(mandant_root: Path, automation_sha: str) -> dict[Path, str]:
    """Ermittelt einheitliche Workflow- und Codepins für einen Mandantenstand."""

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
        rendered = CENTRAL_USES_PATTERN.sub(
            rf"\g<1>{automation_sha}\g<3>", original
        )
        rendered = AUTOMATION_REF_PATTERN.sub(
            rf"\g<1>{automation_sha}\g<3>", rendered
        )
        if rendered != original:
            changes[path] = rendered
    return changes


def _commit(repository: Path, message: str) -> str:
    """Zeigt und committet ausschließlich geänderte Workflowdateien."""

    changed = bool(
        _git(repository, "status", "--short", "--", ".github/workflows").stdout
    )
    if changed:
        _git(repository, "diff", "--check", "--", ".github/workflows")
        print(
            _git(repository, "diff", "--", ".github/workflows").stdout,
            file=sys.stderr,
        )
        _git(
            repository,
            "commit",
            "--no-gpg-sign",
            "--only",
            "-m",
            message,
            "--",
            ".github/workflows",
        )
    return _git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()


def prepare_automation_update(
    automation_root: Path,
    runner_label: str,
    freigegebene_automation_sha: str,
) -> str:
    """Finalisiert die zentrale Automation und gibt ihre Rollout-SHA zurück."""

    if (
        not runner_label.strip()
        or "\n" in runner_label
        or runner_label == RUNNER_PLACEHOLDER
    ):
        raise ValueError(
            "Runner-Kennzeichen muss ein bestätigter einzeiliger Wert der FI sein"
        )
    checkout_sha = _git(
        automation_root, "rev-parse", "--verify", "HEAD^{commit}"
    ).stdout.strip()
    if checkout_sha != freigegebene_automation_sha:
        raise ValueError("zentraler Checkout entspricht nicht der freigegebenen SHA")

    automation_changes = _automation_changes(automation_root, runner_label)
    for path, text in automation_changes.items():
        path.write_text(text, encoding="utf-8")
    automation_sha = _commit(
        automation_root, "Runner der FI in zentralen Workflows aktualisieren"
    )
    if _automation_changes(automation_root, runner_label):
        raise RuntimeError(
            "abschließende Prüfung der zentralen Workflows ist nicht leer"
        )
    return automation_sha


def prepare_mandant_update(
    automation_root: Path,
    mandant_root: Path,
    rollout_sha: str,
) -> str:
    """Erzeugt den lokalen Workflow-Commit eines Mandantenbranches."""

    checkout_sha = _git(
        automation_root, "rev-parse", "--verify", "HEAD^{commit}"
    ).stdout.strip()
    if checkout_sha != rollout_sha:
        raise ValueError("zentraler Checkout entspricht nicht der Rollout-SHA")

    mandant_changes = _mandant_changes(mandant_root, rollout_sha)
    for path, text in mandant_changes.items():
        path.write_text(text, encoding="utf-8")
    mandant_sha = _commit(
        mandant_root, "Zentrale Workflowversion aktualisieren [skip ci]"
    )
    if _mandant_changes(mandant_root, rollout_sha):
        raise RuntimeError(
            "abschließende Prüfung des Mandantenbranches ist nicht leer"
        )
    return mandant_sha


def build_update_matrix(
    mandanten_path: Path,
    releaselinien_path: Path,
) -> dict[str, list[dict[str, str]]]:
    """Bildet alle Mandantenbranches für die aktiven Releaselinien."""

    mandanten = load_mandanten_zuordnung(mandanten_path)
    releaselinien = load_releaselinien_zuordnung(releaselinien_path)

    include = [
        {
            "repository": repository,
            "kuerzel": stammdaten.kuerzel,
            "branch": f"{releaselinie}/{stufe}",
        }
        for repository, stammdaten in sorted(mandanten.items())
        for releaselinie in sorted(releaselinien)
        for stufe in MANDANT_BRANCH_STUFEN
    ]
    return {"include": include}


def build_parser() -> argparse.ArgumentParser:
    """Definiert die drei Schritte des Mandanten-Aktualisierungsworkflows."""

    parser = argparse.ArgumentParser(prog="workflow-configuration")
    commands = parser.add_subparsers(dest="command", required=True)

    automation = commands.add_parser("prepare-automation")
    automation.add_argument("--automation-root", type=Path, required=True)
    automation.add_argument("--runner-label", required=True)
    automation.add_argument("--automation-sha", required=True)

    mandant = commands.add_parser("prepare-mandant")
    mandant.add_argument("--automation-root", type=Path, required=True)
    mandant.add_argument("--mandant-root", type=Path, required=True)
    mandant.add_argument("--rollout-sha", required=True)

    matrix = commands.add_parser("update-matrix")
    matrix.add_argument("--mandanten", type=Path, required=True)
    matrix.add_argument("--releaselinien", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt den ausgewählten Vorbereitungsschritt aus."""

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "prepare-automation":
            result = {
                "rollout_sha": prepare_automation_update(
                    arguments.automation_root,
                    arguments.runner_label,
                    arguments.automation_sha,
                )
            }
        elif arguments.command == "prepare-mandant":
            result = {
                "mandant_sha": prepare_mandant_update(
                    arguments.automation_root,
                    arguments.mandant_root,
                    arguments.rollout_sha,
                )
            }
        elif arguments.command == "update-matrix":
            result = build_update_matrix(
                arguments.mandanten,
                arguments.releaselinien,
            )
        else:
            raise AssertionError(f"unbekanntes Kommando: {arguments.command}")
    except (DeliveryError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(
            f"Mandanten-Aktualisierung kann nicht vorbereitet werden: {error}"
        ) from None
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
