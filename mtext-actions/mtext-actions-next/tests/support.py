"""Stellt kleine gemeinsame Testeingaben bereit."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def git(repository: Path, *arguments: str) -> str:
    """Führt Git in einem temporären Test-Repository aus."""

    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def write_mandant(path: Path) -> None:
    """Schreibt die kleinste produktionsnahe FI-Konfiguration."""

    path.write_text(
        json.dumps(
            {
                "mandant": {
                    "kuerzel": "FI",
                    "repository": "mtext-fi",
                    "subsystem": "LOMS",
                    "hostprofile": {
                        "FKT": {"assignment": "LOMS000066", "stage": "FKTE"},
                        "JUR": {"assignment": "LOMS000067", "stage": "JURP"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

