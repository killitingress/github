"""Bereitet den Rollout freigegebener CI/CD-Versionen in Mandanten-Repositories vor.

Das Werkzeug wird vom Batch-Workflow `update-mandant-workflows` in vier Schritten
aufgerufen:

- `verify-automation` prüft die im zentralen Repository freigegebene Rollout-SHA.
- `update-matrix` erzeugt die Rollout-Matrix für geschützte Mandantenbranches.
- `check-target-branch` prüft, ob ein Matrixeintrag verarbeitet werden kann.
- `prepare-mandant` bindet einen Mandantenbranch an die Rollout-SHA.
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

from lbs_delivery.config import (
    AUTOMATION_ROOT,
    MANDANTEN_ZUORDNUNG_PATH,
    RELEASELINIEN_ZUORDNUNG_PATH,
    load_mandanten_zuordnung,
    load_releaselinien_zuordnung,
)
from lbs_delivery.process import DeliveryError


# Die von Mandanten-Repositories eingebundenen wiederverwendbaren Workflows werden hier gepflegt.
AUTOMATION_REPOSITORY = "FinanzInformatik/fi_lbs_entw_oms_mtext_actions"
# Reguläre Ausdrücke finden die technischen Workflow-Felder dieses Werkzeugs.
# Erfasst die Revision eines wiederverwendbaren Workflows aus dem zentralen
# CI/CD-Repository und erhält Kommentare sowie umgebendes YAML.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)
# Erfasst den Wert `automation_ref` für den Checkout der Python-Implementierung
# und erhält Leerraum sowie einen möglichen nachgestellten YAML-Kommentar.
AUTOMATION_REF_PATTERN = re.compile(r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$")
# GitHub-Antworten werden begrenzt, damit ein fehlerhafter oder vorgeschalteter
# Dienst nicht beliebig viel Runner-Speicher belegen kann.
GITHUB_RESPONSE_LIMIT = 1024 * 1024
# API-Aufrufe erhalten eine feste Wartezeit, damit ein Rollout bei gestörter
# GitHub-Verbindung mit einer verständlichen Fehlermeldung endet.
GITHUB_TIMEOUT = 30.0


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


def _github_request(
    api_url: str,
    path: str,
    token: str,
) -> tuple[int, dict[str, object] | list[object]]:
    """Ruft die GitHub-API ohne Shell auf und begrenzt ihre JSON-Antwort.

    HTTP-Fehler werden als reguläre Statusantworten zurückgegeben, damit ein
    fehlender Release-Branch gezielt behandelt werden kann. Transportfehler und
    ungültige Antworten beenden dagegen den Rollout.
    """

    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/{path.lstrip('/')}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT) as response:
            status = int(response.status)
            response_body = response.read(GITHUB_RESPONSE_LIMIT + 1)
    except urllib.error.HTTPError as error:
        try:
            status = error.code
            response_body = error.read(GITHUB_RESPONSE_LIMIT + 1)
        finally:
            error.close()
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        raise RuntimeError("GitHub-API ist nicht erreichbar") from error
    if len(response_body) > GITHUB_RESPONSE_LIMIT:
        raise RuntimeError("GitHub-API-Antwort ist zu groß")
    try:
        parsed = json.loads(response_body) if response_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("GitHub-API liefert keine gültige JSON-Antwort") from error
    if not isinstance(parsed, (dict, list)):
        raise RuntimeError("GitHub-API-Antwort ist ungültig")
    return status, parsed


def check_target_branch(api_url: str, repository: str, branch: str, token: str) -> bool:
    """Prüft einen geschützten Zielbranch für die Rollout-Matrix.

    Ein fehlender Release-Branch wird übersprungen. `main` muss in jedem
    Mandanten-Repository bestehen. Andere API-Statuswerte zeigen einen echten
    Berechtigungs- oder Betriebsfehler an.
    """

    repository_path = urllib.parse.quote(repository, safe="/")
    branch_path = urllib.parse.quote(branch, safe="")
    status, _ = _github_request(api_url, f"repos/{repository_path}/git/ref/heads/{branch_path}", token)
    if status == 200:
        return True
    if status == 404 and branch != "main":
        return False
    raise RuntimeError(f"Zielbranchprüfung ist mit HTTP {status} fehlgeschlagen")


def _mandant_changes(
    mandant_root: Path,
    automation_sha: str,
) -> dict[Path, str]:
    """Bindet bestehende Mandanten-Workflows an eine freigegebene CI/CD-Version.

    Verweise auf wiederverwendbare Workflows und Python-Checkouts müssen gleich
    häufig vorkommen. Ein Mandant kann dadurch Workflow-YAML und
    Implementierungscode nicht aus unterschiedlichen Revisionen ausführen.
    """

    workflow_root = mandant_root / ".github/workflows"
    workflows = sorted(workflow_root.glob("*.yml"))
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
        # Diff prüfen und für die Protokollierung ausgeben.
        _git(repository, "diff", "--check", "--", ".github/workflows")
        print(_git(repository, "diff", "--", ".github/workflows").stdout, file=sys.stderr)

        # Geänderte Workflow-Dateien committen.
        _git(repository, "commit", "--no-gpg-sign", "--only", "-m", message, "--", ".github/workflows")

    # Aktuelle Revision zurückgeben, auch wenn nichts zu committen war.
    return _git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()


def verify_automation(automation_root: Path, automation_sha: str) -> str:
    """Prüft die freigegebene CI/CD-Version vor dem Mandanten-Rollout.

    Der Checkout muss genau der angegebenen SHA entsprechen und zentrale
    Workflowdateien enthalten.
    """

    checkout_sha = _git(automation_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if checkout_sha != automation_sha:
        raise ValueError("zentraler Checkout entspricht nicht dem angegebenen Commit")
    workflows = sorted((automation_root / ".github/workflows").glob("*.yml"))
    if not workflows:
        raise ValueError("keine zentralen Workflows gefunden")
    return checkout_sha


def prepare_mandant_update(automation_root: Path, mandant_root: Path, rollout_sha: str) -> str:
    """Bindet einen Mandantenbranch an den geprüften zentralen Rollout-Commit.

    Vor Änderungen an Mandantendateien wird der CI/CD-Checkout geprüft.
    Eine zweite Umformung belegt anschließend, dass der Branchstand nach dem
    Commit einheitliche Workflow- und Codereferenzen enthält.
    """

    # CI/CD-Checkout gegen die Rollout-SHA absichern.
    checkout_sha = _git(automation_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if checkout_sha != rollout_sha:
        raise ValueError("zentraler Checkout entspricht nicht der Rollout-SHA")

    # Mandanten-Workflows an den Rollout-Commit binden.
    mandant_changes = _mandant_changes(mandant_root, rollout_sha)
    for path, text in mandant_changes.items():
        path.write_text(text, encoding="utf-8")

    # Änderungen committen.
    mandant_sha = _commit(mandant_root, "Zentrale CI/CD-Version aktualisieren [skip ci]")

    # Abschließende Prüfung der Referenzbindung.
    if _mandant_changes(mandant_root, rollout_sha):
        raise RuntimeError("abschließende Prüfung des Mandantenbranches ist nicht leer")
    return mandant_sha


def build_update_matrix(mandanten_path: Path, releaselinien_path: Path) -> dict[str, list[dict[str, str]]]:
    """Erstellt die Workflow-Matrix für geschützte Mandantenbranches.

    `main` wird in jedem Repository berücksichtigt. Für aktive Releaselinien
    enthält die Matrix mögliche `release/Rnnn`-Branches. Der Workflow überspringt
    einen Eintrag, wenn der betreffende Release-Branch nicht besteht.
    """

    # Zentrale Zuordnungen laden.
    mandanten = load_mandanten_zuordnung(mandanten_path)
    _, releaselinien = load_releaselinien_zuordnung(releaselinien_path)

    # Matrix für main und die möglichen gepflegten Release-Branches aufbauen.
    branches = ["main", *(f"release/{releaselinie}" for releaselinie in sorted(releaselinien))]
    include = [
        {
            "repository": stammdaten.repository,
            "kuerzel": kuerzel,
            "branch": branch,
        }
        for kuerzel, stammdaten in sorted(mandanten.items())
        for branch in branches
    ]
    return {"include": include}


def build_parser() -> argparse.ArgumentParser:
    """Definiert die vier Kommandos des Workflow-Aktualisierungsprozesses.

    Jedes Unterkommando entspricht der Grenze eines Workflow-Jobs und nimmt die
    von diesem Job benötigten Werte entgegen.
    """

    parser = argparse.ArgumentParser(prog="workflow-configuration")
    commands = parser.add_subparsers(dest="command", required=True)

    automation = commands.add_parser(
        "verify-automation",
        help="freigegebene CI/CD-Version prüfen",
    )
    automation.add_argument("--automation-sha", required=True)

    mandant = commands.add_parser(
        "prepare-mandant",
        help="einen Mandantenbranch an die Rollout-SHA binden",
    )
    mandant.add_argument("--mandant-root", type=Path, required=True)
    mandant.add_argument("--rollout-sha", required=True)

    commands.add_parser(
        "update-matrix",
        help="Rollout-Matrix aus Mandanten- und Releaselinienzuordnung erzeugen",
    )

    branch = commands.add_parser(
        "check-target-branch",
        help="Existenz eines geschützten Mandantenbranches prüfen",
    )
    branch.add_argument("--api-url", required=True)
    branch.add_argument("--repository", required=True)
    branch.add_argument("--branch", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt eines der vier Rollout-Kommandos aus und gibt kompaktes JSON aus.

    `verify-automation` und `update-matrix` laufen im zentralen Vorbereitungsjob.
    `prepare-mandant` läuft einmal pro Matrixeintrag im Mandanten-Updatejob.
    """

    arguments = build_parser().parse_args(argv)

    # Rollout-Kommando ausführen.
    try:
        if arguments.command == "verify-automation":
            # Im zentralen Repository freigegebenen Commit prüfen.
            result = {"rollout_sha": verify_automation(AUTOMATION_ROOT, arguments.automation_sha)}
        elif arguments.command == "prepare-mandant":
            # Einen Mandantenbranch an Workflow- und Codereferenzen der Rollout-SHA binden.
            result = {
                "mandant_sha": prepare_mandant_update(AUTOMATION_ROOT, arguments.mandant_root, arguments.rollout_sha)
            }
        elif arguments.command == "update-matrix":
            # Matrix für alle geschützten Mandantenbranches erzeugen.
            result = build_update_matrix(MANDANTEN_ZUORDNUNG_PATH, RELEASELINIEN_ZUORDNUNG_PATH)
        elif arguments.command == "check-target-branch":
            # Matrixeintrag über die GitHub-API prüfen.
            result = check_target_branch(
                arguments.api_url,
                arguments.repository,
                arguments.branch,
                os.environ["WORKFLOW_CONFIGURATION_TOKEN"],
            )
        else:
            raise AssertionError(f"unbekanntes Kommando: {arguments.command}")
    except (DeliveryError, KeyError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Mandanten-Aktualisierung kann nicht vorbereitet werden: {error}") from None

    # Ergebnis als JSON ausgeben.
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
