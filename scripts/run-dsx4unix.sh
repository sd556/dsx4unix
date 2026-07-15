#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_DIR/.venv/bin/python"
ARGS=("$@")
PROFILE="fh4"

if [[ ${#ARGS[@]} -gt 0 && ${ARGS[0]} != -* ]]; then
  PROFILE="${ARGS[0]}"
  ARGS=("${ARGS[@]:1}")
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "error: $VENV_PY not found. Run: uv venv $REPO_DIR/.venv && uv pip install --python $REPO_DIR/.venv/bin/python -e $REPO_DIR" >&2
  exit 1
fi

exec "$VENV_PY" -m dsx4unix --profile "$PROFILE" --verbose "${ARGS[@]}"
