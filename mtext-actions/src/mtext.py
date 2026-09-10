"""Übergibt die Workflow-Kommandos an die zugehörigen M/Text-Module."""

from __future__ import annotations

import argparse

from lbs_delivery import github, lieferung, mainframe, resource_check, sync
from lbs_delivery.process import DeliveryError, Status, execute


def run() -> dict[str, object]:
    """Liest Bereich und Schritt und ruft das zugehörige Modul auf."""

    parser = argparse.ArgumentParser(prog="mtext")
    parser.add_argument("bereich") # z.B. "resources" oder "delivery" oder "release"
    parser.add_argument("schritt") # z.B. "check" oder "sync" oder "github" oder "mainframe"
    parser.add_argument("--tag")
    parser.add_argument("--confirm-direct-delivery", action="store_true") # nur für "delivery"
    args = parser.parse_args()

    if args.bereich == "resources" and args.schritt == "check":
        return resource_check.run()

    if args.bereich == "resources" and args.schritt == "sync":
        return sync.run()

    if args.bereich == "delivery":
        return lieferung.run(args.schritt, args.tag, args.confirm_direct_delivery)

    if args.bereich == "release" and args.schritt == "github":
        return github.run(args.tag)

    if args.bereich == "release" and args.schritt in ("build", "mainframe"):
        return mainframe.run(args.schritt, args.tag)

    raise DeliveryError(Status.VALIDATION_FAILED, f"unbekanntes Kommando: {args.bereich} {args.schritt}")


if __name__ == "__main__":
    raise SystemExit(execute(run))
