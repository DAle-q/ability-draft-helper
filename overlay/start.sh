#!/bin/sh
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=/home/dale/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
if [ ! -x "$PYTHON" ]; then PYTHON=python3; fi
mkdir -p "$ROOT/state"
exec /usr/bin/python3 "$ROOT/overlay/viewer.py" "$PYTHON" --toggle >> "$ROOT/state/overlay.log" 2>&1
