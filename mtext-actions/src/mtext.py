"""Stellt die Kommandos der zentralen M/Text-Automatisierung bereit.

Der Einstieg liest die Workflow-Eingaben und übergibt sie ohne eigene
Fachlogik an die zugehörigen Module.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lbs_delivery import config, github, lieferung, mainframe_release, process, resource_check, sync


def _build_parser() -> argparse.ArgumentParser:
    """Definiert die von den GitHub-Workflows verwendeten Kommandos."""

    parser = argparse.ArgumentParser(prog="mtext")
    commands = parser.add_subparsers(dest="command", required=True)

    # Konfiguration und Ressourcen der Mandantenquelle prüfen.
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

    # Projektpakete bereitstellen und den M/Text-Adapter benachrichtigen.
    synchronize = commands.add_parser("sync-resources", help="Ressourcen mit M/Text synchronisieren")
    synchronize.add_argument("--commit", required=True)
    synchronize.set_defaults(handler=sync.run_command)

    # Lieferung vorprüfen, ihre Ausführung bestätigen oder den Liefer-Tag erzeugen.
    delivery = commands.add_parser("lieferung", help="Lieferung vorprüfen, auflösen, freigeben oder tagen")
    delivery_commands = delivery.add_subparsers(dest="lieferung_command", required=True)

    # Branchstand festhalten und Lieferumfang anzeigen.
    check_delivery = delivery_commands.add_parser("check")
    check_delivery.add_argument("--tag", required=True)
    check_delivery.add_argument("--branch", required=True)
    check_delivery.add_argument("--source-sha", required=True)
    check_delivery.add_argument("--actor", required=True)
    check_delivery.set_defaults(handler=lieferung.run_command)

    # Geplanten oder vorhandenen Liefer-Tag dem nächsten Schritt zuordnen.
    resolve_delivery = delivery_commands.add_parser("aufloesen")
    resolve_delivery.add_argument("--tag", required=True)
    resolve_delivery.add_argument("--api-url", required=True)
    resolve_delivery.set_defaults(handler=lieferung.run_aufloesen)

    # Lokal geladene Vorbereitung durch dieselbe oder eine zweite Person bestätigen.
    execute_delivery = delivery_commands.add_parser("ausfuehren")
    execute_delivery.add_argument("--tag", required=True)
    execute_delivery.add_argument("--vorbereitung", type=Path, required=True)
    execute_delivery.add_argument("--actor", required=True)
    execute_delivery.add_argument("--direktlieferung-bestaetigt", action="store_true")
    execute_delivery.set_defaults(handler=lieferung.run_command)

    # Liefer-Tag auf der festgehaltenen SHA erzeugen.
    tag_delivery = delivery_commands.add_parser("tag")
    tag_delivery.add_argument("--tag", required=True)
    tag_delivery.add_argument("--branch", required=True)
    tag_delivery.add_argument("--source-sha", required=True)
    tag_delivery.add_argument("--api-url", required=True)
    tag_delivery.set_defaults(handler=lieferung.run_command)

    # Release-Dateien erzeugen, an den Mainframe übergeben und Lieferinformationen veröffentlichen.
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

    return parser


def run() -> dict[str, object]:
    """Führt das gewählte Workflow-Kommando aus."""

    arguments = _build_parser().parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(process.execute(run))
