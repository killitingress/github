"""Definiert die vier Kommandos der Lieferautomation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .config import AUTOMATION_ROOT, load_configuration
from .errors import DeliveryError, Status
from .mainframe import publish_mainframe
from .release import build_release
from .sync import sync_resources


def build_parser() -> argparse.ArgumentParser:
    """Baut die zu den wiederverwendbaren Workflows passende CLI."""

    parser = argparse.ArgumentParser(prog="lbs-delivery")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate-config")

    sync = commands.add_parser("sync-resources")
    sync.add_argument("--commit", required=True)

    release = commands.add_parser("build-release")
    release.add_argument("--tag", required=True)
    release.add_argument("--trigger-sha", default="")

    commands.add_parser("publish-mainframe")
    return parser


def run(arguments: argparse.Namespace) -> dict[str, object]:
    """Führt den vom Parser ausgewählten fachlichen Ablauf aus."""

    workspace = Path(os.environ["GITHUB_WORKSPACE"])

    if arguments.command == "publish-mainframe":
        with tempfile.TemporaryDirectory(
            prefix="jcl-",
            dir=os.environ["RUNNER_TEMP"],
        ) as temporary:
            return publish_mainframe(
                manifest_path=workspace / "dist" / "manifest.json",
                artifact_root=workspace / "dist",
                template_path=AUTOMATION_ROOT / "templates/mainframe-upload.jcl",
                temporary_directory=temporary,
                execute=True,
            )

    repository_name = os.environ["GITHUB_REPOSITORY"]
    repository_root = workspace / "source"
    configuration = load_configuration(repository_root, repository_name)
    if arguments.command == "validate-config":
        result = {
            "status": Status.CONFIG_VALIDATED.value,
            "mandanten_kuerzel": configuration.kuerzel,
            "repository": configuration.repository,
            "releaselinien": sorted(configuration.releaselinien),
        }
    elif arguments.command == "sync-resources":
        with tempfile.TemporaryDirectory(
            prefix="resources-",
            dir=os.environ["RUNNER_TEMP"],
        ) as staging:
            result = sync_resources(
                configuration,
                repository_root=repository_root,
                commit=arguments.commit,
                source_branch=os.environ["GITHUB_REF_NAME"],
                staging_root=staging,
                execute=True,
            )
    elif arguments.command == "build-release":
        manifest = build_release(
            configuration,
            repository_root=repository_root,
            output_directory=workspace / "dist",
            tag=arguments.tag,
            trigger_sha=arguments.trigger_sha,
        )
        result = {
            "status": Status.ARTIFACT_READY.value,
            "manifest": str(manifest),
        }
    else:
        raise AssertionError(f"unbekanntes Kommando: {arguments.command}")
    if configuration.warnungen:
        result["warnungen"] = list(configuration.warnungen)
    return result


def main(argv: list[str] | None = None) -> int:
    """Gibt ein JSON-Ergebnis aus und übersetzt fachliche Fehler."""

    try:
        result = run(build_parser().parse_args(argv))
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except KeyError as exc:
        print(
            f"{Status.VALIDATION_FAILED.value}: "
            f"GitHub-Runnerkontext fehlt: {exc.args[0]}",
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError) as exc:
        print(
            f"{Status.VALIDATION_FAILED.value}: lokale Dateioperation fehlgeschlagen: {exc}",
            file=sys.stderr,
        )
        return 2
    for warnung in result.get("warnungen", []):
        print(f"WARNUNG: {warnung}", file=sys.stderr)
    print(json.dumps(result, sort_keys=True))
    return 0
