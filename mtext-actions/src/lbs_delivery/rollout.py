"""Aktualisiert die gebundene CI/CD-Version in Mandanten-Workflows.

Der zentrale Rollout prüft die gewünschte Revision, ermittelt seine Ziele und
schreibt die neue SHA in die wiederverwendbaren Workflow-Aufrufe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

from . import config, git, github
from .process import DeliveryError, Status


# Die von Mandanten-Repositories eingebundenen wiederverwendbaren Workflows werden hier gepflegt.
AUTOMATION_REPOSITORY = "FinanzInformatik/fi_lbs_entw_oms_mtext_actions"

# Reguläre Ausdrücke finden die technischen Workflow-Felder dieses Werkzeugs.
# Erfasst die Revision eines wiederverwendbaren Workflows aus dem zentralen CI/CD-Repository.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)

# Erfasst den Wert automation_ref für den Checkout der Python-Implementierung.
AUTOMATION_REF_PATTERN = re.compile(r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$")


def check_target_branch(api_url: str, repository: str, branch: str, token: str) -> bool:
    """Prüft, ob ein Zielbranch der Rollout-Matrix vorhanden ist."""

    repository_path = urllib.parse.quote(repository)
    branch_path = urllib.parse.quote(branch, safe="")
    return (
        github.request(
            method="GET",
            url=f"{api_url.rstrip('/')}/repos/{repository_path}/git/ref/heads/{branch_path}",
            token=token,
            failure=Status.SOURCE_FAILED,
            missing_ok=True,
        )
        is not None
    )


def _workflow_update(path: Path, automation_sha: str) -> str | None:
    """Ermittelt den an die Rollout-SHA gebundenen Inhalt einer Workflow-Datei."""

    original = path.read_text(encoding="utf-8")
    workflow_references = list(CENTRAL_USES_PATTERN.finditer(original))
    if not workflow_references:
        return None
    code_references = list(AUTOMATION_REF_PATTERN.finditer(original))
    if len(workflow_references) != len(code_references):
        raise DeliveryError(Status.VALIDATION_FAILED, f"CI/CD-Version ist in {path} unvollständig gebunden")
    rendered = AUTOMATION_REF_PATTERN.sub(
        rf"\g<1>{automation_sha}\g<3>",
        CENTRAL_USES_PATTERN.sub(rf"\g<1>{automation_sha}\g<3>", original),
    )
    return rendered if rendered != original else None


def _pending_workflow_updates(mandant_root: Path, automation_sha: str) -> dict[Path, str]:
    """Ermittelt Mandanten-Workflows, die noch nicht an die Rollout-SHA gebunden sind."""

    workflow_root = mandant_root / ".github/workflows"
    return {
        path: update
        for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")))
        if (update := _workflow_update(path, automation_sha)) is not None
    }


def _commit(repository: Path, message: str) -> str:
    """Committet geänderte Workflow-Dateien und gibt die aktuelle SHA zurück."""

    if git.run(repository, "status", "--short", "--", ".github/workflows"):
        git.run(repository, "diff", "--check", "--", ".github/workflows")
        print(git.run(repository, "diff", "--", ".github/workflows").decode(), file=sys.stderr)
        git.run(repository, "commit", "--no-gpg-sign", "--only", "-m", message, "--", ".github/workflows")
    return git.run(repository, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()


def verify_automation(automation_root: Path, automation_sha: str) -> str:
    """Prüft die angegebene CI/CD-Version vor dem Mandanten-Rollout."""

    checkout_sha = git.run(automation_root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if checkout_sha != automation_sha:
        raise DeliveryError(Status.SOURCE_FAILED, "zentraler Checkout entspricht nicht dem angegebenen Commit")
    if not list((automation_root / ".github/workflows").glob("*.yml")):
        raise DeliveryError(Status.VALIDATION_FAILED, "keine zentralen Workflows gefunden")
    return checkout_sha


def prepare_mandant_update(automation_root: Path, mandant_root: Path, rollout_sha: str) -> str:
    """Trägt die Rollout-SHA in die zentralen Verweise eines Mandantenbranches ein."""

    verify_automation(automation_root, rollout_sha)
    pending = _pending_workflow_updates(mandant_root, rollout_sha)
    for path, text in pending.items():
        path.write_text(text, encoding="utf-8")
    # Die bereits geänderten Dateien müssen nach dem Schreiben vollständig gebunden sein.
    if any(_workflow_update(path, rollout_sha) is not None for path in pending):
        raise DeliveryError(Status.VALIDATION_FAILED, "CI/CD-Version konnte nicht vollständig gebunden werden")
    return _commit(mandant_root, "Zentrale CI/CD-Version aktualisieren [skip ci]")


def build_update_matrix(mandanten_path: Path, releaselinien_path: Path) -> dict[str, list[dict[str, str]]]:
    """Erstellt die Workflow-Matrix für geschützte Mandantenbranches."""

    mandanten = config.load_mandanten_zuordnung(mandanten_path)
    _, releaselinien = config.load_releaselinien_zuordnung(releaselinien_path)
    branches = ["main", *(f"release/{releaselinie}" for releaselinie in sorted(releaselinien))]
    return {
        "include": [
            {"repository": stammdaten.repository, "kuerzel": kuerzel, "branch": branch}
            for kuerzel, stammdaten in sorted(mandanten.items())
            for branch in branches
        ]
    }


def run_command(arguments: argparse.Namespace) -> dict[str, object]:
    """Führt das gewählte Kommando der Mandanten-Aktualisierung aus."""

    if arguments.rollout_command == "prepare-rollout":
        verify_automation(config.AUTOMATION_ROOT, arguments.automation_sha)
        matrix = build_update_matrix(config.MANDANTEN_ZUORDNUNG_PATH, config.RELEASELINIEN_ZUORDNUNG_PATH)
        return {
            "outputs": {
                "rollout_sha": arguments.automation_sha,
                "update_matrix": json.dumps(matrix, separators=(",", ":")),
            },
        }
    if arguments.rollout_command == "prepare-mandant":
        return {"mandant_sha": prepare_mandant_update(config.AUTOMATION_ROOT, arguments.mandant_root, arguments.rollout_sha)}

    exists = check_target_branch(
        arguments.api_url,
        arguments.repository,
        arguments.branch,
        os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
    )
    return {"outputs": {"exists": str(exists).lower()}}
