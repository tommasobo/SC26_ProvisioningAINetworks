#!/usr/bin/env bash
# Redraw the submission figures from compact, committed data.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${ARTIFACT_PYTHON:-}" ]]; then
    PYTHON_BIN="$ARTIFACT_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
else
    PYTHON_BIN="$(command -v python3)"
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(
        "Python 3.10 or newer is required. Create .venv as described in README.md."
    )
for module in ("matplotlib", "numpy", "pandas"):
    try:
        __import__(module)
    except ImportError as exc:
        raise SystemExit(
            "Missing plotting dependency %r. Install requirements.txt." % exc.name
        )
PY

export MPLBACKEND="${MPLBACKEND:-Agg}"
exec "$PYTHON_BIN" "$ROOT/reproduce_all.py" --only 1 3 4 5 6 7 8 9 10 "$@"
