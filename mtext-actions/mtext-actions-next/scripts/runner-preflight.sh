#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 0 ]]; then
  echo "usage: runner-preflight.sh" >&2
  exit 2
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
required_python="$(tr -d '[:space:]' < "$script_dir/../.python-version")"

for command_name in git python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "missing runner command: $command_name" >&2
    exit 2
  fi
done

actual_python="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$actual_python" != "$required_python" ]]; then
  echo "runner Python must be $required_python, found $actual_python" >&2
  exit 2
fi

git --version
python3 --version

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "python=$(command -v python3)" >> "$GITHUB_OUTPUT"
else
  command -v python3
fi

