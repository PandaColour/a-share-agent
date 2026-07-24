#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$SCRIPT_DIR"

if command -v caffeinate >/dev/null 2>&1; then
    exec caffeinate -dimsu "$PYTHON_BIN" win_main.py "$@"
fi

exec "$PYTHON_BIN" win_main.py "$@"
