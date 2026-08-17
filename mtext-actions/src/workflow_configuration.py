"""Trägt eine CI/CD-Version in die Workflows der Mandanten-Repositories ein.

Das Werkzeug wird vom Batch-Workflow `update-mandant-workflows` in drei Schritten
aufgerufen: `prepare-rollout`, `check-target-branch` und `prepare-mandant`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lbs_delivery import config, process


# Die von Mandanten-Repositories eingebundenen wiederverwendbaren Workflows werden hier gepflegt.
AUTOMATION_REPOSITORY = "FinanzInformatik/fi_lbs_entw_oms_mtext_actions"

# Reguläre Ausdrücke finden die technischen Workflow-Felder dieses Werkzeugs.
# Erfasst die Revision eines wiederverwendbaren Workflows aus dem zentralen CI/CD-Repository.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)

# Erfasst den Wert `automation_ref` für den Checkout der Python-Implementierung.
AUTOMATION_REF_PATTERN = re.compile(r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$")


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Führt einen Git-Befehl im Mandanten- oder CI/CD-Repository aus."""

    try:
        return subprocess.run(["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True)
    except OSError as error:
        raise RuntimeError("Git ist für die Mandanten-Aktualisierung nicht verfügbar") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"Git-Operation fehlgeschlagen: {detail}") from None


def _github_status(api_url: str, path: str, token: str) -> int:
    """Fragt den HTTP-Status einer GitHub-Ressource ab."""

    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/{path.lstrip('/')}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=process.NETWORK_TIMEOUT) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise RuntimeError("GitHub-API ist nicht erreichbar") from error


def check_target_branch(api_url: str, repository: str, branch: str, token: str) -> bool:
    """Prüft, ob ein Zielbranch der Rollout-Matrix vorhanden ist."""

    repository_path = urllib.parse.quote(repository)
    branch_path = urllib.parse.quote(branch, safe="")
    status = _github_status(api_url, f"repos/{repository_path}/git/ref/heads/{branch_path}", token)

    if status == 200:
        return True

    if status == 404:
        return False

    raise RuntimeError(f"Zielbranchprüfung ist mit HTTP {status} fehlgeschlagen")


def _assert_mandant_bound(mandant_root: Path, automation_sha: str) -> dict[Path, str]:
    """Ermittelt Mandanten-Workflows, die noch nicht an die Rollout-SHA gebunden sind.

    Ein leeres Ergebnis bedeutet, dass alle zentralen Verweise die Rollout-SHA tragen.
    """

    workflow_root = mandant_root / ".github/workflows"
    pending: dict[Path, str] = {}

    for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
        original = path.read_text(encoding="utf-8")
        workflow_references = list(CENTRAL_USES_PATTERN.finditer(original))

        if not workflow_references:
            continue

        code_references = list(AUTOMATION_REF_PATTERN.finditer(original))
        if len(workflow_references) != len(code_references):
            raise ValueError(f"CI/CD-Version ist in {path} unvollständig gebunden")

        rendered = AUTOMATION_REF_PATTERN.sub(
            rf"\g<1>{automation_sha}\g<3>",
            CENTRAL_USES_PATTERN.sub(rf"\g<1>{automation_sha}\g<3>", original),
        )

        if rendered != original:
            pending[path] = rendered

    return pending


def _commit(repository: Path, message: str) -> str:
    """Committet geänderte Workflow-Dateien und gibt die aktuelle SHA zurück."""

    if _git(repository, "status", "--short", "--", ".github/workflows").stdout:
        _git(repository, "diff", "--check", "--", ".github/workflows")
        print(_git(repository, "diff", "--", ".github/workflows").stdout, file=sys.stderr)
        _git(repository, "commit", "--no-gpg-sign", "--only", "-m", message, "--", ".github/workflows")
    return _git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()


def verify_automation(automation_root: Path, automation_sha: str) -> str:
    """Prüft die angegebene CI/CD-Version vor dem Mandanten-Rollout."""

    checkout_sha = _git(automation_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if checkout_sha != automation_sha:
        raise ValueError("zentraler Checkout entspricht nicht dem angegebenen Commit")

    if not list((automation_root / ".github/workflows").glob("*.yml")):
        raise ValueError("keine zentralen Workflows gefunden")

    return checkout_sha


def prepare_mandant_update(automation_root: Path, mandant_root: Path, rollout_sha: str) -> str:
    """Trägt die Rollout-SHA in die zentralen Verweise eines Mandantenbranches ein."""

    verify_automation(automation_root, rollout_sha)
    for path, text in _assert_mandant_bound(mandant_root, rollout_sha).items():
        path.write_text(text, encoding="utf-8")

    mandant_sha = _commit(mandant_root, "Zentrale CI/CD-Version aktualisieren [skip ci]")

    if _assert_mandant_bound(mandant_root, rollout_sha):
        raise RuntimeError("Mandanten-Workflows sind nach dem Rollout noch nicht vollständig an die Rollout-SHA gebunden")

    return mandant_sha


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


def build_parser() -> argparse.ArgumentParser:
    """Definiert die drei Kommandos für die Workflow-Aktualisierung."""

    parser = argparse.ArgumentParser(prog="workflow-configuration")
    commands = parser.add_subparsers(dest="command", required=True)

    rollout = commands.add_parser("prepare-rollout", help="CI/CD-Version prüfen und Rollout-Ziele erstellen")
    rollout.add_argument("--automation-sha", required=True)

    mandant = commands.add_parser("prepare-mandant", help="einen Mandantenbranch an die Rollout-SHA binden")
    mandant.add_argument("--mandant-root", type=Path, required=True)
    mandant.add_argument("--rollout-sha", required=True)

    branch = commands.add_parser("check-target-branch", help="Existenz eines geschützten Mandantenbranches prüfen")
    branch.add_argument("--api-url", required=True)
    branch.add_argument("--repository", required=True)
    branch.add_argument("--branch", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt eines der drei Rollout-Kommandos aus und gibt kompaktes JSON aus."""

    arguments = build_parser().parse_args(argv)
    try:
        match arguments.command:
            case "prepare-rollout":
                verify_automation(config.AUTOMATION_ROOT, arguments.automation_sha)
                result = build_update_matrix(config.MANDANTEN_ZUORDNUNG_PATH, config.RELEASELINIEN_ZUORDNUNG_PATH)
            case "prepare-mandant":
                result = {
                    "mandant_sha": prepare_mandant_update(
                        config.AUTOMATION_ROOT, arguments.mandant_root, arguments.rollout_sha
                    )
                }
            case "check-target-branch":
                result = check_target_branch(
                    arguments.api_url,
                    arguments.repository,
                    arguments.branch,
                    os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
                )
                if not result:
                    print(
                        f"::warning title=Rollout-Ziel fehlt::{arguments.repository} "
                        f"besitzt den Branch {arguments.branch} nicht und wird übersprungen",
                        file=sys.stderr,
                    )
            case _:
                raise AssertionError(f"unbekanntes Kommando: {arguments.command}")
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Mandanten-Aktualisierung kann nicht vorbereitet werden: {error}") from None

    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
