"""Übergibt die Workflow-Kommandos an die zugehörigen M/Text-Module."""

from __future__ import annotations

import argparse

from lbs_delivery import config, github, lieferung, mainframe, process, resource_check, sync


def _build_parser() -> argparse.ArgumentParser:
    """Definiert die von den GitHub-Workflows verwendeten Kommandos."""

    # erster Name wählt den fachlichen Bereich, der zweite den Workflow-Schritt
    parser = argparse.ArgumentParser(prog="mtext")
    commands = parser.add_subparsers(required=True)

    # Konfiguration und Ressourcen benötigen keine zusätzlichen Eingaben
    config_commands = commands.add_parser("config").add_subparsers(required=True)
    config_commands.add_parser("validate").set_defaults(handler=config.run)

    resource_commands = commands.add_parser("resources").add_subparsers(required=True)
    resource_commands.add_parser("check").set_defaults(handler=resource_check.run)
    resource_commands.add_parser("sync").set_defaults(handler=sync.run)

    # Lieferkommandos übergeben Liefer-Tag und ausgewählten Schritt an denselben Einstieg
    delivery_commands = commands.add_parser("delivery").add_subparsers(required=True)
    for name in ("check", "resolve", "tag"):
        command_parser = delivery_commands.add_parser(name)
        command_parser.add_argument("--tag", required=True)
        command_parser.set_defaults(handler=lieferung.run, subcommand=name)

    # Bestätigung trägt zusätzlich die bewusste Freigabe einer Direktlieferung
    confirm_delivery = delivery_commands.add_parser("confirm")
    confirm_delivery.add_argument("--tag", required=True)
    confirm_delivery.add_argument("--confirm-direct-delivery", action="store_true")
    confirm_delivery.set_defaults(handler=lieferung.run, subcommand="confirm")

    # Releasebau und Mainframe-Übergabe teilen den Einstieg, GitHub veröffentlicht danach
    release_commands = commands.add_parser("release").add_subparsers(required=True)

    build_release = release_commands.add_parser("build")
    build_release.add_argument("--tag", required=True)
    build_release.set_defaults(handler=mainframe.run, subcommand="build")

    release_commands.add_parser("mainframe").set_defaults(handler=mainframe.run, subcommand="mainframe")

    github_release = release_commands.add_parser("github")
    github_release.add_argument("--tag", required=True)
    github_release.set_defaults(handler=github.run)

    return parser


def run() -> dict[str, object]:
    """Führt das gewählte Workflow-Kommando aus."""

    # gewählten Moduleinstieg entnehmen und ausschließlich seine echten Parameter übergeben
    arguments = vars(_build_parser().parse_args())
    handler = arguments.pop("handler")
    return handler(**arguments)


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
