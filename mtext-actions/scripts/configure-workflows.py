#!/usr/bin/env python3
"""Finalisiert zentrale und mandantenseitige Workflowdateien idempotent."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path


# Dieses Repository ist die einzige freigegebene Quelle wiederverwendbarer Workflows.
AUTOMATION_REPOSITORY = "j520730/mtext-actions"
# Der Nullwert kennzeichnet eine noch nicht freigegebene zentrale Workflowversion.
NULL_SHA = "0" * 40
# Dieses Runner-Kennzeichen markiert die noch ausstehende Festlegung durch FI.
RUNNER_PLACEHOLDER = "FI_RUNNER_LABEL_TO_BE_SET"

# Reguläre Ausdrücke erkennen nur die technischen Felder der Workflowdateien.
# Erfasst den skalaren runs-on-Wert jedes zentral definierten Jobs.
RUNS_ON_PATTERN = re.compile(r"(?m)^(\s*runs-on:\s*).+$")
# Erfasst den Versionsanteil eines Aufrufs der drei zentralen Workflows.
CENTRAL_USES_PATTERN = re.compile(
    rf"(?m)^(\s*uses:\s+{re.escape(AUTOMATION_REPOSITORY)}"
    r"/\.github/workflows/[^\s@]+@)([^\s#]+)(\s*(?:#.*)?)$"
)
# Erfasst den technischen Checkout-Pin der zentralen Python-Implementierung.
AUTOMATION_REF_PATTERN = re.compile(
    r"(?m)^(\s*automation_ref:\s*)([^\s#]+)(\s*(?:#.*)?)$"
)


def render_automation_workflow(text: str, runner_label: str, path: Path) -> str:
    """Setzt das FI-Runner-Kennzeichen in allen Jobs eines zentralen Workflows."""

    rendered, replacements = RUNS_ON_PATTERN.subn(
        rf"\g<1>{json.dumps(runner_label)}", text
    )
    if replacements == 0:
        raise ValueError(f"kein runs-on-Feld in {path}")
    return rendered


def render_mandant_workflow(
    text: str, automation_sha: str, path: Path
) -> tuple[str, bool]:
    """Bindet beide Pins gemeinsam und meldet ihren abweichenden Ausgangszustand."""

    workflow_references = list(CENTRAL_USES_PATTERN.finditer(text))
    code_references = list(AUTOMATION_REF_PATTERN.finditer(text))
    if not workflow_references or not code_references:
        raise ValueError(f"zentrale Workflowreferenzen fehlen in {path}")
    if len(workflow_references) != len(code_references):
        raise ValueError(
            f"Workflowaufrufe und automation_ref sind unvollständig in {path}"
        )

    pin_mismatch = any(
        workflow_reference.group(2) != code_reference.group(2)
        for workflow_reference, code_reference in zip(
            workflow_references, code_references
        )
    )
    rendered = CENTRAL_USES_PATTERN.sub(
        rf"\g<1>{automation_sha}\g<3>", text
    )
    rendered = AUTOMATION_REF_PATTERN.sub(
        rf"\g<1>{automation_sha}\g<3>", rendered
    )
    return rendered, pin_mismatch


def write_atomic(path: Path, text: str) -> None:
    """Ersetzt eine geprüfte Workflowdatei atomar im vorhandenen Verzeichnis."""

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write(text)
        os.chmod(temporary_path, path.stat().st_mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    """Prüft alle Dateien vorab und schreibt nur auf ausdrückliche Anforderung."""

    parser = argparse.ArgumentParser(
        description="Plant oder schreibt die zentral festgelegten Workflowwerte."
    )
    parser.add_argument("--automation-sha", required=True)
    parser.add_argument("--runner-label", required=True)
    parser.add_argument(
        "--automation-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--mandant-root",
        action="append",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Schreibt die geprüften Änderungen; ohne diese Option bleibt der Lauf "
            "lesend."
        ),
    )
    arguments = parser.parse_args()

    # Prüft eine vollständige kleingeschriebene Git-SHA ohne bewegliche Referenz.
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.automation_sha):
        raise SystemExit(
            "--automation-sha muss eine vollständige kleingeschriebene SHA sein"
        )
    if arguments.automation_sha == NULL_SHA:
        raise SystemExit("--automation-sha darf nicht der technische Nullwert sein")
    if (
        not arguments.runner_label.strip()
        or "\n" in arguments.runner_label
        or arguments.runner_label == RUNNER_PLACEHOLDER
    ):
        raise SystemExit(
            "--runner-label muss ein bestätigtes einzeiliges FI-Kennzeichen sein"
        )

    changed: dict[Path, str] = {}
    pin_mismatches: list[Path] = []
    try:
        automation_workflows = sorted(
            (arguments.automation_root / ".github/workflows").glob("*.yml")
        )
        if not automation_workflows:
            raise SystemExit("keine zentralen Workflows gefunden")
        for path in automation_workflows:
            original = path.read_text(encoding="utf-8")
            rendered = render_automation_workflow(
                original, arguments.runner_label, path
            )
            if rendered != original:
                changed[path] = rendered

        for mandant_root in arguments.mandant_root:
            mandant_workflows = sorted(
                (mandant_root / ".github/workflows").glob("*.yml")
            )
            if not mandant_workflows:
                raise SystemExit(
                    f"keine Mandanten-Workflows unter {mandant_root} gefunden"
                )
            for path in mandant_workflows:
                original = path.read_text(encoding="utf-8")
                rendered, pin_mismatch = render_mandant_workflow(
                    original, arguments.automation_sha, path
                )
                if pin_mismatch:
                    pin_mismatches.append(path)
                if rendered != original:
                    changed[path] = rendered
    except (OSError, ValueError) as error:
        raise SystemExit(
            f"Einrichtung kann nicht vorbereitet werden: {error}"
        ) from None

    if arguments.apply:
        try:
            for path, text in changed.items():
                write_atomic(path, text)
        except OSError as error:
            raise SystemExit(
                "Einrichtung wurde nicht vollständig geschrieben; "
                f"nach Behebung erneut ausführen: {error}"
            ) from None
    print(
        json.dumps(
            {
                "status": "APPLIED" if arguments.apply else "PLANNED",
                "changed_files": [str(path) for path in changed],
                "pin_mismatches": [str(path) for path in pin_mismatches],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
