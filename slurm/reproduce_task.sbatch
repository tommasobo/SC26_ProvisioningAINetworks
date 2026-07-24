#!/usr/bin/env bash
#SBATCH --job-name=sc26-artifact
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=96G
#SBATCH --time=01:00:00

set -euo pipefail

: "${ARTIFACT_ROOT:?ARTIFACT_ROOT is required}"
: "${ARTIFACT_TASK:?ARTIFACT_TASK is required}"
: "${ARTIFACT_SCRATCH:?ARTIFACT_SCRATCH is required}"

cd "$ARTIFACT_ROOT"

if [[ -x "$ARTIFACT_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ARTIFACT_ROOT/.venv/bin/python"
else
    PYTHON_BIN="${ARTIFACT_PYTHON:-python3}"
fi

args=(
    "$PYTHON_BIN"
    scripts/reproduce_full_task.py
    --task "$ARTIFACT_TASK"
    --scratch "$ARTIFACT_SCRATCH"
    --workers "${ARTIFACT_WORKERS:-4}"
)
if [[ -n "${ARTIFACT_GROK_ANALYSIS_DIR:-}" ]]; then
    args+=(--grok-analysis-dir "$ARTIFACT_GROK_ANALYSIS_DIR")
fi

exec /usr/bin/time -v "${args[@]}"
