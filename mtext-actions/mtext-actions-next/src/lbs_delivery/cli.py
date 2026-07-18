"""Definiert die vier Kommandos der Lieferautomation."""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_configuration
from .errors import DeliveryError, Status
from .mainframe import publish_mainframe
from .release import build_release
from .sync import sync_resources


def _add_configuration_arguments(parser: argparse.ArgumentParser) -> None:
    """Ergänzt die drei Kommandos mit gemeinsamer Lieferkonfiguration."""

    parser.add_argument("--mandant-config", default=".config.json")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--releaselinien", required=True)
    parser.add_argument("--repository-name", required=True)


def build_parser() -> argparse.ArgumentParser:
    """Baut die zu den wiederverwendbaren Workflows passende CLI."""

    parser = argparse.ArgumentParser(prog="lbs-delivery")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-config")
    _add_configuration_arguments(validate)

    sync = commands.add_parser("sync-resources")
    _add_configuration_arguments(sync)
    sync.add_argument("--commit", required=True)
    sync.add_argument("--source-branch", required=True)
    sync.add_argument("--environment", required=True)
    sync.add_argument("--staging-dir", required=True)
    sync.add_argument("--timeout", type=float, default=60.0)
    sync.add_argument("--execute", action="store_true")

    release = commands.add_parser("build-release")
    _add_configuration_arguments(release)
    release.add_argument("--tag", required=True)
    release.add_argument("--trigger-sha", default="")
    release.add_argument("--output", default="dist")

    publish = commands.add_parser("publish-mainframe")
    publish.add_argument("--manifest", required=True)
    publish.add_argument("--artifact-root", required=True)
    publish.add_argument("--template", required=True)
    publish.add_argument("--temporary-dir", required=True)
    publish.add_argument("--execute", action="store_true")
    return parser


def run(arguments: argparse.Namespace) -> dict[str, object]:
    """Führt genau den vom Parser ausgewählten fachlichen Ablauf aus."""

    if arguments.command == "publish-mainframe":
        return publish_mainframe(
            manifest_path=arguments.manifest,
            artifact_root=arguments.artifact_root,
            template_path=arguments.template,
            temporary_directory=arguments.temporary_dir,
            execute=arguments.execute,
        )

    configuration = load_configuration(
        arguments.mandant_config,
        arguments.releaselinien,
        repository_name=arguments.repository_name,
        repository_root=arguments.repository_root,
    )
    if arguments.command == "validate-config":
        return {
            "status": Status.CONFIG_VALIDATED.value,
            "mandanten_kuerzel": configuration.kuerzel,
            "repository": configuration.repository,
            "releaselinien": sorted(configuration.releaselinien),
        }
    if arguments.command == "sync-resources":
        return sync_resources(
            configuration,
            repository_root=arguments.repository_root,
            commit=arguments.commit,
            source_branch=arguments.source_branch,
            environment=arguments.environment,
            staging_root=arguments.staging_dir,
            timeout=arguments.timeout,
            execute=arguments.execute,
        )
    if arguments.command == "build-release":
        manifest = build_release(
            configuration,
            repository_root=arguments.repository_root,
            output_directory=arguments.output,
            repository_name=arguments.repository_name,
            tag=arguments.tag,
            trigger_sha=arguments.trigger_sha,
        )
        return {
            "status": Status.ARTIFACT_READY.value,
            "manifest": str(manifest),
        }
    raise AssertionError(f"unbekanntes Kommando: {arguments.command}")


def main(argv: list[str] | None = None) -> int:
    """Gibt genau ein JSON-Ergebnis aus und übersetzt fachliche Fehler."""

    try:
        result = run(build_parser().parse_args(argv))
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, UnicodeError) as exc:
        print(
            f"{Status.VALIDATION_FAILED.value}: lokale Dateioperation fehlgeschlagen: {exc}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0
