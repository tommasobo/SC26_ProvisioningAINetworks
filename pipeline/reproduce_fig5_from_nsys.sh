#!/usr/bin/env bash
# Optional reproduction of paper Figure 5 starting from raw nsys captures.
#
# Stages:
#   1. Download 4 nsys-rep files for Llama7B N4/GPU16 from the trace server.
#   2. nsys export --type=sqlite   (needs NVIDIA Nsight Systems)
#   3. tools/nccl_generator        (SQLite -> output.goal + metadata sidecars)
#   4. Composite LP               (metadata -> composed_runtime.csv, Gurobi)
#   5. Optional patched LogGOPSim (GOAL -> comm_dep.csv)
#   6. Optional Monolithic LP     (GOAL + comm_dep -> full_runtime.csv)
#
# Requires: nsys >= 2024.x on PATH, Python 3.10+, wget, and Gurobi.
# The larger Monolithic LP is disabled unless --run-lp is passed.
#
# Local-safe checks:
#   pipeline/reproduce_fig5_from_nsys.sh --dry-run
#   pipeline/reproduce_fig5_from_nsys.sh --skip-download --work tier_c_fig5
#
# Full optional run:
#   pipeline/reproduce_fig5_from_nsys.sh --run-lp

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

WORK="${WORK:-$ROOT/tier_c_fig5}"
A2_NSYS="${A2_NSYS:-http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N4_GPU16_TP1_PP1_DP16_BS32_1iter/raw_nsys/}"
RUN_LP=0
DRY_RUN=0
SKIP_DOWNLOAD=0
WORKERS=4
NSYS_DIR=""

if [[ -n "${ARTIFACT_PYTHON:-}" ]]; then
    PYTHON_BIN="$ARTIFACT_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
else
    PYTHON_BIN="$(command -v python3)"
fi
NSYS_BIN="${NSYS_BIN:-nsys}"

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --dry-run          Print planned commands and dependency status, then exit.
  --run-lp           Run the larger Monolithic-LP and LogGOPSim sweeps.
                     Without this flag, the Composite-LP analysis still runs.
  --skip-download    Use existing files under WORK/nsys instead of running wget.
  --work DIR         Working directory (default: \$WORK or $ROOT/tier_c_fig5).
  --nsys-dir DIR     Use an existing directory of .nsys-rep files.
  --workers N        Parallel Composite-LP workers (default: 4).
  --a2-nsys URL      nsys URL (default: $A2_NSYS).
  -h, --help         Show this help.

The standard path downloads only the selected Fig. 5 nsys subtree and runs
the Composite-LP analysis. Use --run-lp only for the larger optional sweeps.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --run-lp)
            RUN_LP=1
            ;;
        --skip-download)
            SKIP_DOWNLOAD=1
            ;;
        --work)
            shift
            if [ "$#" -eq 0 ]; then
                echo "error: --work requires a directory argument" >&2
                exit 2
            fi
            WORK="$1"
            ;;
        --workers)
            shift
            if [ "$#" -eq 0 ]; then
                echo "error: --workers requires a positive integer" >&2
                exit 2
            fi
            WORKERS="$1"
            ;;
        --nsys-dir)
            shift
            if [ "$#" -eq 0 ]; then
                echo "error: --nsys-dir requires a directory" >&2
                exit 2
            fi
            NSYS_DIR="$1"
            SKIP_DOWNLOAD=1
            ;;
        --a2-nsys)
            shift
            if [ "$#" -eq 0 ]; then
                echo "error: --a2-nsys requires a URL argument" >&2
                exit 2
            fi
            A2_NSYS="$1"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

[[ "$WORKERS" =~ ^[1-9][0-9]*$ ]] || {
    echo "error: --workers must be a positive integer" >&2
    exit 2
}
if [[ -z "$NSYS_DIR" ]]; then
    NSYS_DIR="$WORK/nsys"
fi

require_cmd() {
    local name="$1"
    local why="$2"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "error: '$name' is required for $why" >&2
        exit 3
    fi
}

check_python_module() {
    local module="$1"
    "$PYTHON_BIN" - "$module" <<'PY'
import importlib.util
import sys
mod = sys.argv[1]
sys.exit(0 if importlib.util.find_spec(mod) else 1)
PY
}

print_plan() {
    cat <<EOF
Tier C plan:
  work directory : $WORK
  nsys URL       : $A2_NSYS
  nsys directory : $NSYS_DIR
  skip download  : $SKIP_DOWNLOAD
  run LP         : $RUN_LP
  workers        : $WORKERS

Steps:
  1. Download selected Fig. 5 .nsys-rep files unless --skip-download is set.
  2. Export .nsys-rep files to sqlite with nsys.
  3. Run tools/nccl_generator through pipeline/run_nccl_generator.py.
  4. Regenerate the Composite-LP sensitivity curve from the fresh metadata.
  5. If --run-lp is set, emit comm_dep.csv via patched LogGOPSim and run
     the expensive Gurobi monolithic LP sweep.
EOF
}

print_plan

if [ "$DRY_RUN" -eq 1 ]; then
    echo
    echo "Dependency status:"
    for cmd in "$PYTHON_BIN" wget "$NSYS_BIN"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            echo "  [ok]      $cmd"
        else
            echo "  [missing] $cmd"
        fi
    done
    for module in pandas numba tqdm gurobipy; do
        if check_python_module "$module"; then
            echo "  [ok]      python:$module"
        else
            echo "  [missing] python:$module"
        fi
    done
    echo
    echo "Dry run complete. No dependency is required for --dry-run, and no files were downloaded or generated."
    exit 0
fi

require_cmd "$PYTHON_BIN" "Tier C Python wrappers"
if [ "$SKIP_DOWNLOAD" -eq 0 ]; then
    require_cmd wget "downloading selected Fig. 5 nsys files"
fi
require_cmd "$NSYS_BIN" "exporting nsys-rep files to sqlite"

for module in pandas numba tqdm gurobipy; do
    if ! check_python_module "$module"; then
        echo "error: Python module '$module' is required. Run: pip install -r requirements-tierc.txt" >&2
        exit 3
    fi
done

mkdir -p "$NSYS_DIR" "$WORK"/{sqlite,analysis,out}

echo "=== [1/5] Prepare nsys-rep files ==="
if [ "$SKIP_DOWNLOAD" -eq 0 ]; then
    wget -nc -r -np -nH --cut-dirs=5 -A '*.nsys-rep' -P "$NSYS_DIR" "$A2_NSYS"
    while IFS= read -r rep; do
        flat="$NSYS_DIR/$(basename "$rep")"
        if [ "$rep" != "$flat" ] && [ ! -e "$flat" ]; then
            ln -s "$rep" "$flat"
        fi
    done < <(find "$NSYS_DIR" -mindepth 2 -type f -name '*.nsys-rep')
else
    echo "  [skip] using existing files under $NSYS_DIR"
fi

shopt -s nullglob
reps=("$NSYS_DIR"/*.nsys-rep)
if [ "${#reps[@]}" -eq 0 ]; then
    echo "error: no .nsys-rep files found under $NSYS_DIR" >&2
    echo "       remove --skip-download or set --work to a directory with nsys files." >&2
    exit 4
fi
printf '  %s\n' "${reps[@]}"

echo "=== [2/5] nsys export --type=sqlite ==="
for rep in "${reps[@]}"; do
    sqlite="$WORK/sqlite/$(basename "${rep%.nsys-rep}.sqlite")"
    if [ -f "$sqlite" ]; then
        echo "  [skip] $sqlite exists"
        continue
    fi
    "$NSYS_BIN" export --type=sqlite -o "$sqlite" "$rep"
done

echo "=== [3/5] SQLite -> GOAL via nccl_generator ==="
"$PYTHON_BIN" "$HERE/run_nccl_generator.py" \
    --sqlite-dir "$WORK/sqlite" \
    --out-dir    "$WORK/analysis"

echo "=== [4/5] Fresh metadata -> Composite-LP sensitivity curve ==="
"$PYTHON_BIN" "$HERE/run_nccl_composite.py" \
    --analysis-dir "$WORK/analysis" \
    --out "$WORK/out/composed_runtime.csv" \
    --cache-dir "$WORK/out/composite_cache" \
    --clear-cache \
    --node-map-mode rank-block \
    --ring-duplicate-policy last \
    --nic-per-rank \
    --parallel-solve \
    --max-workers "$WORKERS" \
    --l-min 0 --l-max 1000000 --step 5000

echo "=== Fresh result -> paper-style Figure 5 plot ==="
SC26_DATA_ROOT="$ROOT/data" \
SC26_FIGURE_DIR="$WORK/figures" \
SC26_FIG5_RESULT_DIR="$WORK/out" \
MPLBACKEND=Agg \
"$PYTHON_BIN" "$ROOT/scripts/fig05_llama_iteration.py"

if [ "$RUN_LP" -eq 0 ]; then
    echo
    echo "Figure 5 Composite-LP reproduction complete."
    echo "Regenerated CSV: $WORK/out/composed_runtime.csv"
    echo "Regenerated plot: $WORK/figures/fig5_llama7b.pdf"
    echo "Use --run-lp to add the larger Monolithic-LP sweep."
    exit 0
fi

echo "=== Optional GOAL -> comm_dep.csv via patched LogGOPSim ==="
"$PYTHON_BIN" "$HERE/run_lgs.py" \
    --goal "$WORK/analysis/output.goal" \
    --L 1000 --G 0.04 --o 200 \
    --comm-dep-out "$WORK/analysis/comm_dep.csv"

echo "=== Optional GOAL + comm_dep -> Monolithic-LP sweep ==="
"$PYTHON_BIN" "$HERE/run_monolithic_lp.py" \
    --goal  "$WORK/analysis/output.goal" \
    --comm-dep "$WORK/analysis/comm_dep.csv" \
    --out   "$WORK/out/full_runtime.csv" \
    --l-min 0 --l-max 1000000 --step 50000

echo "=== Optional GOAL -> LogGOPSim sweep ==="
"$PYTHON_BIN" "$HERE/run_lgs_sweep.py" \
    --goal "$WORK/analysis/output.goal" \
    --out "$WORK/out/lgs_runtime.csv" \
    --latencies 0 25000 50000 100000 200000 500000 1000000 \
    --G 0.04 --o 200

echo "=== Fresh optional results -> paper-style Figure 5 plot ==="
SC26_DATA_ROOT="$ROOT/data" \
SC26_FIGURE_DIR="$WORK/figures" \
SC26_FIG5_RESULT_DIR="$WORK/out" \
SC26_FIG5_MONOLITHIC_RESULT="$WORK/out/full_runtime.csv" \
SC26_FIG5_LGS_RESULT="$WORK/out/lgs_runtime.csv" \
MPLBACKEND=Agg \
"$PYTHON_BIN" "$ROOT/scripts/fig05_llama_iteration.py"

SHIPPED="$ROOT/data/output/llama7b/partial_100pct/sweeps/full_runtime.csv"
MY="$WORK/out/full_runtime.csv"

"$PYTHON_BIN" - <<PY
import json
from pathlib import Path

import numpy as np
import pandas as pd

shipped = pd.read_csv("$SHIPPED")
mine    = pd.read_csv("$MY")
shipped = shipped.sort_values("L")
mine = mine.sort_values("L")
actual = mine[(mine["L"] >= shipped["L"].min()) & (mine["L"] <= shipped["L"].max())].copy()
actual["runtime_shipped_interp"] = np.interp(actual["L"], shipped["L"], shipped["runtime"])
actual["abs_diff_ns"] = (actual["runtime_shipped_interp"] - actual["runtime"]).abs()
actual["rel_diff"] = actual["abs_diff_ns"] / actual["runtime_shipped_interp"].abs()

comparison_dir = Path("$WORK/out/comparison")
comparison_dir.mkdir(parents=True, exist_ok=True)
detail_path = comparison_dir / "fig5_monolithic_vs_shipped_detail.csv"
summary_path = comparison_dir / "fig5_monolithic_vs_shipped_summary.json"
actual.to_csv(detail_path, index=False)

summary = {
    "expected": "$SHIPPED",
    "actual": "$MY",
    "n_points": int(len(actual)),
    "min_L": float(actual["L"].min()) if len(actual) else None,
    "max_L": float(actual["L"].max()) if len(actual) else None,
    "max_abs_diff_ns": float(actual["abs_diff_ns"].max()) if len(actual) else None,
    "mean_abs_diff_ns": float(actual["abs_diff_ns"].mean()) if len(actual) else None,
    "max_abs_rel_diff_pct": float(actual["rel_diff"].max() * 100.0) if len(actual) else None,
    "mean_abs_rel_diff_pct": float(actual["rel_diff"].mean() * 100.0) if len(actual) else None,
    "detail_csv": str(detail_path),
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

print(json.dumps(summary, indent=2))
print(f"comparison detail: {detail_path}")
print(f"comparison summary: {summary_path}")
PY

echo
echo "Tier C end-to-end reproduction complete."
echo "Regenerated CSV: $MY"
echo "The shipped figure path remains unchanged. Inspect the regenerated CSV before replacing packaged data."
