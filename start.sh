#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "$0")"
export OPENBLAS_NUM_THREADS=1
bundled_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
python_command=python3
if [[ -x "$bundled_python" ]] && "$bundled_python" -c 'import PIL,numpy,tkinter' 2>/dev/null; then
    python_command="$bundled_python"
fi
if [[ "${1:-}" == '--capture' ]]; then
    shift
    exec "$python_command" capture.py "$@"
fi
exec "$python_command" app.py "$@"
