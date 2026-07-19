"""Bereitet die zentralen und mandantenseitigen Workflow-Commits vor."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


# Dieses Repository ist die freigegebene Quelle der wiederverwendbaren Workflows.
AUTOMATION_REPOSITORY = "j520730/mtext-actions"
# Dieses Kennzeichen markiert die noch ausstehende Festlegung des Runners der FI.
RUNNER_PLACEHOLDER = "FI_RUNNER_LABEL_TO_BE_SET"
# Nur der Einrichtungsworkflow benötigt zur Bootstrap-Zeit einen variablen Runner.
CONFIGURATION_WORKFLOW = "configure-workflows.yml"

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
        raise RuntimeError("Git ist für die Einrichtung nicht verfügbar") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Git-Operation fehlgeschlagen: {detail}") from None


def _automation_changes(automation_root: Path, runner_label: str) -> dict[Path, str]:
    """Ermittelt die festen Runnerwerte der zentralen Fach- und Testworkflows."""

    workflows = sorted(
        path
        for path in (automation_root / ".github/workflows").glob("*.yml")
        if path.name != CONFIGURATION_WORKFLOW
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
        print(_git(repository, "diff", "--", ".github/workflows").stdout)
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


def prepare_workflow_configuration(
    automation_root: Path,
    mandant_root: Path,
    runner_label: str,
    freigegebene_automation_sha: str,
) -> str:
    """Erzeugt beide lokalen Commits und erzwingt den vollständigen Zielzustand."""

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

    # Beide Dateisätze werden vollständig validiert, bevor eine Datei geändert wird.
    automation_changes = _automation_changes(automation_root, runner_label)
    _mandant_changes(mandant_root, freigegebene_automation_sha)

    for path, text in automation_changes.items():
        path.write_text(text, encoding="utf-8")
    automation_sha = _commit(
        automation_root, "Runner der FI in zentralen Workflows einrichten"
    )

    mandant_changes = _mandant_changes(mandant_root, automation_sha)
    for path, text in mandant_changes.items():
        path.write_text(text, encoding="utf-8")
    _commit(mandant_root, "Zentrale Workflowversion einrichten [skip ci]")

    if _automation_changes(automation_root, runner_label) or _mandant_changes(
        mandant_root, automation_sha
    ):
        raise RuntimeError("abschließende Einrichtungsprüfung ist nicht leer")
    return automation_sha


def main() -> int:
    """Stellt dem GitHub-Workflow die vorbereiteten Commits bereit."""

    try:
        automation_sha = prepare_workflow_configuration(
            Path("automation"),
            Path("mandant"),
            os.environ.get("FI_RUNNER_LABEL", ""),
            os.environ.get("AUTOMATION_SHA", ""),
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Einrichtung kann nicht vorbereitet werden: {error}") from None

    print(f"Einrichtung geprüft: zentrale Version {automation_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
