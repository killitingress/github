"""Stellt die Kommandos der zentralen M/Text-Automatisierung bereit.

Der Einstieg liest die Workflow-Eingaben und übergibt sie ohne eigene
Fachlogik an die zugehörigen Module.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lbs_delivery import config, github, mainframe_release, process, release_approval, resource_check, rollout, sync


def build_parser() -> argparse.ArgumentParser:
    """Definiert die von den GitHub-Workflows verwendeten Kommandos."""

    parser = argparse.ArgumentParser(prog="mtext")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate-config", help="Mandantenkonfiguration prüfen").set_defaults(handler=config.run_validation)

    check = commands.add_parser("check-resources", help="JSON- und XML-Ressourcen prüfen")
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--formats", type=Path, required=True)
    check.add_argument("--changed-only", action="store_true")
    check.set_defaults(
        handler=lambda arguments: resource_check.run(
            root=arguments.root.resolve(),
            formats_path=arguments.formats,
            changed_only=arguments.changed_only,
        )
    )

    synchronize = commands.add_parser("sync-resources", help="Ressourcen mit M/Text synchronisieren")
    synchronize.add_argument("--commit", required=True)
    synchronize.set_defaults(handler=sync.run_command)

    approval = commands.add_parser("release-approval", help="Release-Freigabe vorbereiten oder abschließen")
    approval_commands = approval.add_subparsers(dest="approval_command", required=True)
    prepare = approval_commands.add_parser("prepare")
    prepare.add_argument("--tag", required=True)
    prepare.add_argument("--branch", required=True)
    prepare.add_argument("--source-sha", required=True)
    prepare.add_argument("--run-reference", required=True)
    prepare.set_defaults(handler=release_approval.run_command)
    check_approval = approval_commands.add_parser("check")
    check_approval.add_argument("--approval-branch", required=True)
    check_approval.add_argument("--branch", required=True)
    check_approval.add_argument("--target-sha", required=True)
    check_approval.set_defaults(handler=release_approval.run_command)
    finalize = approval_commands.add_parser("finalize")
    finalize.add_argument("--approval-branch", required=True)
    finalize.add_argument("--branch", required=True)
    finalize.add_argument("--merge-sha", required=True)
    finalize.add_argument("--pull-request-number", type=int, required=True)
    finalize.add_argument("--api-url", required=True)
    finalize.set_defaults(handler=release_approval.run_command)

    release = commands.add_parser("build-release", help="Release-Dateien erstellen")
    release.add_argument("--tag", required=True)
    release.add_argument("--trigger-sha", default="")
    release.set_defaults(handler=mainframe_release.run_build_command)
    commands.add_parser("publish-mainframe", help="Release an den Mainframe übergeben").set_defaults(
        handler=mainframe_release.run_publish_command
    )
    commands.add_parser("publish-github-release", help="Lieferinformationen veröffentlichen").set_defaults(
        handler=github.run_publish_command
    )

    rollout_parser = commands.add_parser("rollout", help="Mandanten-Workflows aktualisieren")
    rollout_commands = rollout_parser.add_subparsers(dest="rollout_command", required=True)
    rollout_prepare = rollout_commands.add_parser("prepare-rollout")
    rollout_prepare.add_argument("--automation-sha", required=True)
    rollout_prepare.set_defaults(handler=rollout.run_command)
    rollout_mandant = rollout_commands.add_parser("prepare-mandant")
    rollout_mandant.add_argument("--mandant-root", type=Path, required=True)
    rollout_mandant.add_argument("--rollout-sha", required=True)
    rollout_mandant.set_defaults(handler=rollout.run_command)
    rollout_branch = rollout_commands.add_parser("check-target-branch")
    rollout_branch.add_argument("--api-url", required=True)
    rollout_branch.add_argument("--repository", required=True)
    rollout_branch.add_argument("--branch", required=True)
    rollout_branch.set_defaults(handler=rollout.run_command)

    return parser


def run() -> dict[str, object]:
    """Führt das gewählte Workflow-Kommando aus."""

    arguments = build_parser().parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
