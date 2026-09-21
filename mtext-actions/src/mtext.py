"""Übergibt die Workflow-Kommandos an die zugehörigen M/Text-Module."""

from __future__ import annotations

import argparse
import os

from lbs_delivery import config, git, lieferung, mainframe, resource_check, sync
from lbs_delivery.process import DeliveryError, Status, execute
from lbs_delivery.project_packages import Scope, lieferumfang


def run() -> dict[str, object]:
    """Liest Bereich und Schritt und ruft das zugehörige Modul auf."""

    parser = argparse.ArgumentParser(prog="mtext")
    parser.add_argument("section") # z.B. "resources" oder "delivery" oder "release"
    parser.add_argument("subcommand") # z.B. "check" oder "sync" oder "mainframe"
    parser.add_argument("--tag")
    parser.add_argument("--issue", type=int) # Freigabe-Issue einer Lieferung
    parser.add_argument("--delivery-scope", action="store_true") # Umfang der folgenden Lieferung
    parser.add_argument("--sync-scope", action="store_true") # Umfang der folgenden Synchronisierung
    args = parser.parse_args()

    if args.section == "resources" and args.subcommand == "check":
        # Der Workflow-Aufruf legt genau einen fachlichen Prüfungsumfang fest.
        if args.delivery_scope and args.sync_scope:
            raise DeliveryError(Status.VALIDATION_FAILED, "Prüfungsumfang ist nicht eindeutig")

        if args.tag:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag wird aus dem Branch ermittelt")

        scope: Scope | None = None
        if args.delivery_scope:
            source = config.mandant_source()
            configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])
            tag = lieferung.liefer_tag_for_branch(configuration, os.environ["GITHUB_REF_NAME"])
            scope = lieferumfang(source, tag, git.resolve(source, "HEAD"))
        elif args.sync_scope:
            source = config.mandant_source()
            configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])
            scope = sync.resolve_plan(source, configuration).scope

        # Der Syntaxprüfer verarbeitet den fertigen Scope ohne Kenntnis des Folgejobs.
        return resource_check.run(scope)

    if args.section == "resources" and args.subcommand == "sync":
        return sync.run()

    if args.section == "delivery":
        return lieferung.run(args.subcommand, args.tag, args.issue)

    if args.section == "release" and args.subcommand in ("build", "mainframe"):
        return mainframe.run(args.subcommand, args.tag)

    raise DeliveryError(Status.VALIDATION_FAILED, f"unbekanntes Kommando: {args.section} {args.subcommand}")


if __name__ == "__main__":
    raise SystemExit(execute(run))
