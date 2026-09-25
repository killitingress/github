"""Startet die Testsuite mit den lokalen Python-Quellen."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


# Repository-Pfade unabhängig vom aktuellen Arbeitsverzeichnis bestimmen
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPOSITORY_ROOT / "src"
TEST_ROOT = REPOSITORY_ROOT / "tests"


def main() -> int:
    """Bindet die Quellen ein und meldet das Ergebnis der Testsuite zurück."""

    # isolierte Python-Runtimes kennen den lokalen Quellpfad nicht
    sys.path.insert(0, str(SOURCE_ROOT))

    # Tests als Paket laden, damit gemeinsame Testaufbauten erreichbar sind
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT),
        top_level_dir=str(REPOSITORY_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
