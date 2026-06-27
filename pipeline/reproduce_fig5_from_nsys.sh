#!/usr/bin/env bash
# Optional reproduction of paper Figure 5 starting from raw nsys captures.
#
# Stages:
#   1. Download 4 nsys-rep files for Llama7B N4/GPU16 from the trace server.
#   2. nsys export --type=sqlite   (needs NVIDIA Nsight Systems)
#   3. tools/nccl_generator        (SQLite -> output.goal + metadata sidecars)
#   4. patched LogGOPSim           (GOAL -> comm_dep.csv)
#   5. solver/main.py              (GOAL + comm_dep -> full_runtime.csv, Gurobi)
#   6. scripts/fig05_llama_iteration.py  (CSV -> fig5_llama7b.pdf)
#   7. Diff regenerated CSV and PDF against the shipped artifact output.
#
# Requires: nsys >= 2024.x on PATH, Python 3.8+, wget. The LP step also
# requires Gurobi and is disabled unless --run-lp is passed.
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

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --dry-run          Print planned commands and dependency status, then exit.
  --run-lp           Run the expensive Monolithic-LP sweep. Without this flag,
                     the script stops after GOAL generation.
  --skip-download    Use existing files under WORK/nsys instead of running wget.
  --work DIR         Working directory (default: \$WORK or $ROOT/tier_c_fig5).
  --a2-nsys URL      nsys URL (default: $A2_NSYS).
  -h, --help         Show this help.

This script is intentionally not part of the default local reproduction path.
It downloads only the selected Fig. 5 nsys subtree, never the full trace
archive, and requires --run-lp before launching the expensive Gurobi LP stage.
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
    python3 - "$module" <<'PY'
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
  skip download  : $SKIP_DOWNLOAD
  run LP         : $RUN_LP

Steps:
  1. Download selected Fig. 5 .nsys-rep files unless --skip-download is set.
  2. Export .nsys-rep files to sqlite with nsys.
  3. Run tools/nccl_generator through pipeline/run_nccl_generator.py.
  4. Stop unless --run-lp is set.
  5. If --run-lp is set, emit comm_dep.csv via patched LogGOPSim and run
     the expensive Gurobi monolithic LP sweep.
EOF
}

print_plan

if [ "$DRY_RUN" -eq 1 ]; then
    echo
    echo "Dependency status:"
    for cmd in python3 wget nsys; do
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

require_cmd python3 "Tier C Python wrappers"
if [ "$SKIP_DOWNLOAD" -eq 0 ]; then
    require_cmd wget "downloading selected Fig. 5 nsys files"
fi
require_cmd nsys "exporting nsys-rep files to sqlite"

for module in pandas numba tqdm; do
    if ! check_python_module "$module"; then
        echo "error: Python module '$module' is required. Run: pip install -r requirements-tierc.txt" >&2
        exit 3
    fi
done

if [ "$RUN_LP" -eq 1 ] && ! check_python_module gurobipy; then
    echo "error: gurobipy is required for --run-lp. Install/configure Gurobi first." >&2
    exit 3
fi

mkdir -p "$WORK"/{nsys,sqlite,analysis,out}

echo "=== [1/5] Prepare nsys-rep files ==="
if [ "$SKIP_DOWNLOAD" -eq 0 ]; then
    wget -nc -r -np -nH --cut-dirs=5 -A '*.nsys-rep' -P "$WORK/nsys" "$A2_NSYS"
    while IFS= read -r rep; do
        flat="$WORK/nsys/$(basename "$rep")"
        if [ "$rep" != "$flat" ] && [ ! -e "$flat" ]; then
            ln -s "$rep" "$flat"
        fi
    done < <(find "$WORK/nsys" -mindepth 2 -type f -name '*.nsys-rep')
else
    echo "  [skip] --skip-download set; using existing files under $WORK/nsys"
fi

shopt -s nullglob
reps=("$WORK/nsys"/*.nsys-rep)
if [ "${#reps[@]}" -eq 0 ]; then
    echo "error: no .nsys-rep files found under $WORK/nsys" >&2
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
    nsys export --type=sqlite -o "$sqlite" "$rep"
done

echo "=== [3/5] SQLite -> GOAL via nccl_generator ==="
python3 "$HERE/run_nccl_generator.py" \
    --sqlite-dir "$WORK/sqlite" \
    --out-dir    "$WORK/analysis"

if [ "$RUN_LP" -eq 0 ]; then
    echo
    echo "Tier C stopped before the expensive Monolithic-LP step."
    echo "To continue with Gurobi, rerun with --run-lp."
    exit 0
fi

echo "=== [4/6] GOAL -> comm_dep.csv via patched LogGOPSim ==="
python3 "$HERE/run_lgs.py" \
    --goal "$WORK/analysis/output.goal" \
    --L 1000 --G 0.04 --o 200 \
    --comm-dep-out "$WORK/analysis/comm_dep.csv"

echo "=== [5/6] GOAL + comm_dep -> Monolithic-LP sweep (paper Fig 5 baseline, can take tens of minutes) ==="
python3 "$HERE/run_monolithic_lp.py" \
    --goal  "$WORK/analysis/output.goal" \
    --comm-dep "$WORK/analysis/comm_dep.csv" \
    --out   "$WORK/out/full_runtime.csv" \
    --l-min 0 --l-max 1000000 --step 50000

echo "=== [6/6] Compare regenerated vs shipped (Monolithic LP baseline) ==="
cp "$WORK/out/full_runtime.csv" \
   "$ROOT/data/output/llama7b/partial_100pct/sweeps/full_runtime.csv.regenerated"
echo "  regenerated CSV saved to:"
echo "    $ROOT/data/output/llama7b/partial_100pct/sweeps/full_runtime.csv.regenerated"

SHIPPED="$ROOT/data/output/llama7b/partial_100pct/sweeps/full_runtime.csv"
MY="$WORK/out/full_runtime.csv"

python3 - <<PY
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sys

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
if len(actual) and actual["rel_diff"].max() < 1e-3:
    print("\\nPASS: regenerated CSV matches shipped within 0.1%.")
    sys.exit(0)
print("\\nWARN: regenerated CSV differs from shipped by more than 0.1%.")
sys.exit(1)
PY

echo
echo "Tier C end-to-end reproduction complete."
echo "Regenerated CSV: $MY"
echo "The shipped figure path remains unchanged. Inspect the regenerated CSV before replacing packaged data."
