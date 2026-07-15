#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: runner-preflight.sh REQUIREMENTS_LOCK" >&2
  exit 2
fi

requirements_lock="$1"
required_python="$(tr -d '[:space:]' < "$(dirname "$requirements_lock")/.python-version")"

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

if [[ ! -f "$requirements_lock" ]]; then
  echo "requirements lock is missing" >&2
  exit 2
fi
if [[ -z "${LBS_WHEELHOUSE:-}" || ! -d "$LBS_WHEELHOUSE" ]]; then
  echo "LBS_WHEELHOUSE must point to the approved internal wheelhouse" >&2
  exit 2
fi
if [[ -z "${RUNNER_TEMP:-}" || ! -d "$RUNNER_TEMP" ]]; then
  echo "RUNNER_TEMP is missing" >&2
  exit 2
fi

venv="$RUNNER_TEMP/lbs-delivery-venv-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
if [[ -e "$venv" ]]; then
  echo "isolated Python environment already exists: $venv" >&2
  exit 2
fi

python3 -m venv "$venv"
"$venv/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-index \
  --find-links "$LBS_WHEELHOUSE" \
  --requirement "$requirements_lock"
"$venv/bin/python" -c 'import jsonschema; assert jsonschema.__version__ == "4.26.0"'

git --version
"$venv/bin/python" --version

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "python=$venv/bin/python" >> "$GITHUB_OUTPUT"
else
  echo "$venv/bin/python"
fi
