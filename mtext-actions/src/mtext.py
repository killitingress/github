"""Übergibt die Workflow-Kommandos an die zugehörigen M/Text-Module."""

from __future__ import annotations

import argparse
import os

from lbs_delivery import config, git, github, lieferung, mainframe, resource_check, sync
from lbs_delivery.process import DeliveryError, Status, execute
from lbs_delivery.project_packages import Scope, release_scope


def run() -> dict[str, object]:
    """Liest Bereich und Schritt und ruft das zugehörige Modul auf."""

    parser = argparse.ArgumentParser(prog="mtext")
    parser.add_argument("bereich") # z.B. "resources" oder "delivery" oder "release"
    parser.add_argument("schritt") # z.B. "check" oder "sync" oder "github" oder "mainframe"
    parser.add_argument("--tag")
    parser.add_argument("--issue", type=int) # Freigabe-Issue einer Lieferung
    parser.add_argument("--delivery-scope", action="store_true") # Umfang der folgenden Lieferung
    parser.add_argument("--sync-scope", action="store_true") # Umfang der folgenden Synchronisierung
    args = parser.parse_args()

    if args.bereich == "resources" and args.schritt == "check":
        # Der Workflow-Aufruf legt genau einen fachlichen Prüfungsumfang fest.
        if args.delivery_scope and args.sync_scope:
            raise DeliveryError(Status.VALIDATION_FAILED, "Prüfungsumfang ist nicht eindeutig")

        if args.tag:
            raise DeliveryError(Status.VALIDATION_FAILED, "Liefer-Tag wird aus dem Branch ermittelt")

        scope: Scope | None = None
        if args.delivery_scope:
            source = config.mandant_source()
            configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])
            tag = lieferung.liefer_tag_fuer_branch(configuration, os.environ["GITHUB_REF_NAME"])
            scope = release_scope(source, tag, git.resolve(source, "HEAD"))
        elif args.sync_scope:
            source = config.mandant_source()
            configuration = config.Configuration.load(source, os.environ["GITHUB_REPOSITORY"])
            scope = sync.resolve_plan(source, configuration).scope

        # Der Syntaxprüfer verarbeitet den fertigen Scope ohne Kenntnis des Folgejobs.
        return resource_check.run(scope)

    if args.bereich == "resources" and args.schritt == "sync":
        return sync.run()

    if args.bereich == "delivery":
        return lieferung.run(args.schritt, args.tag, args.issue)

    if args.bereich == "release" and args.schritt == "github":
        return github.run(args.tag)

    if args.bereich == "release" and args.schritt in ("build", "mainframe"):
        return mainframe.run(args.schritt, args.tag)

    raise DeliveryError(Status.VALIDATION_FAILED, f"unbekanntes Kommando: {args.bereich} {args.schritt}")


if __name__ == "__main__":
    raise SystemExit(execute(run))
