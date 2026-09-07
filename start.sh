#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$0")"
export OPENBLAS_NUM_THREADS=1
bundled_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ -x "$bundled_python" ]] && "$bundled_python" -c 'import PIL,numpy,tkinter' 2>/dev/null; then
    exec "$bundled_python" app.py "$@"
fi
exec python3 app.py "$@"
