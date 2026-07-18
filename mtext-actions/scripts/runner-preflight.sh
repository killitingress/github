#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "Aufruf: runner-preflight.sh" >&2
  exit 2
fi

# Skriptverzeichnis ermitteln und Python-Mindestversion aus .python-version lesen.
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
minimum_python="$(tr -d '[:space:]' < "$script_dir/../.python-version")"

# Prüfen ob Git und Python 3 auf dem Runner verfügbar sind.
for command_name in git python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Fehlender Befehl auf dem Runner: $command_name" >&2
    exit 2
  fi
done

# Python-Haupt- und Nebenversion auslesen und mit der Mindestversion vergleichen.
actual_python="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
IFS=. read -r minimum_major minimum_minor <<< "$minimum_python"
IFS=. read -r actual_major actual_minor <<< "$actual_python"

if ((actual_major < minimum_major || (actual_major == minimum_major && actual_minor < minimum_minor))); then
  echo "Python-Version des Runners muss mindestens $minimum_python sein, gefunden: $actual_python" >&2
  exit 2
fi

git --version
python3 --version

# Python-Pfad in GitHub-Output schreiben oder auf Standardausgabe ausgeben.
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "python=$(command -v python3)" >> "$GITHUB_OUTPUT"
else
  command -v python3
fi
