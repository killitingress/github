"""Stellt die Kommandos der gemeinsamen M/Text-Automatisierung bereit.

Der Einstieg liest die Workflow-Eingaben und übergibt sie ohne eigene
Fachlogik an die zugehörigen Module.
"""

from __future__ import annotations

import argparse

from lbs_delivery import config, github, lieferung, mainframe_release, process, resource_check, sync


def _build_parser() -> argparse.ArgumentParser:
    """Definiert die von den GitHub-Workflows verwendeten Kommandos."""

    parser = argparse.ArgumentParser(prog="mtext")
    commands = parser.add_subparsers(dest="command", required=True)

    config_parser = commands.add_parser("config", help="Mandantenkonfiguration prüfen")
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("validate", help="Mandantenkonfiguration prüfen").set_defaults(handler=config.run)

    resources = commands.add_parser("resources", help="Ressourcen prüfen oder mit M/Text synchronisieren")
    resource_commands = resources.add_subparsers(dest="resources_command", required=True)
    resource_commands.add_parser("check", help="JSON- und XML-Ressourcen prüfen").set_defaults(handler=resource_check.run)
    resource_commands.add_parser("sync", help="Ressourcen mit M/Text synchronisieren").set_defaults(handler=sync.run)

    delivery = commands.add_parser("delivery", help="Lieferstand vorbereiten, ermitteln, bestätigen oder taggen")
    delivery_commands = delivery.add_subparsers(dest="delivery_command", required=True)

    check_delivery = delivery_commands.add_parser("check")
    check_delivery.add_argument("--tag", required=True)
    check_delivery.set_defaults(handler=lieferung.run)

    resolve_delivery = delivery_commands.add_parser("resolve")
    resolve_delivery.add_argument("--tag", required=True)
    resolve_delivery.set_defaults(handler=lieferung.run)

    confirm_delivery = delivery_commands.add_parser("confirm")
    confirm_delivery.add_argument("--tag", required=True)
    confirm_delivery.add_argument("--confirm-direct-delivery", action="store_true")
    confirm_delivery.set_defaults(handler=lieferung.run)

    tag_delivery = delivery_commands.add_parser("tag")
    tag_delivery.add_argument("--tag", required=True)
    tag_delivery.set_defaults(handler=lieferung.run)

    release = commands.add_parser("release", help="Lieferdateien bauen, übertragen oder veröffentlichen")
    release_commands = release.add_subparsers(dest="release_command", required=True)

    build_release = release_commands.add_parser("build", help="Release-Dateien erstellen")
    build_release.add_argument("--tag", required=True)
    build_release.set_defaults(handler=mainframe_release.run)

    release_commands.add_parser("mainframe", help="Release an den Mainframe übergeben").set_defaults(
        handler=mainframe_release.run
    )

    github_release = release_commands.add_parser("github", help="Lieferinformationen veröffentlichen")
    github_release.add_argument("--tag", required=True)
    github_release.set_defaults(handler=github.run)

    return parser


def run() -> dict[str, object]:
    """Führt das gewählte Workflow-Kommando aus."""

    arguments = _build_parser().parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
