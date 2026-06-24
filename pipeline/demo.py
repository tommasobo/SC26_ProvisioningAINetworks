#!/usr/bin/env python3
"""
End-to-end pipeline demonstration.

Runs both upstream stages (Composite-LP sweep + LogGOPSim replay) on
the small 16-rank, 1 MiB ring-AllReduce GOAL trace shipped under
``data/traces/`` and prints a summary. This exercise is what the paper
applies at production scale (Llama 70B, Grok 314B, vLLM 8B) — the
Composite-LP sweep produces the sensitivity CSVs consumed by the
figure scripts, and LGS produces the validation runtimes overlaid on
those figures.

The demo typically completes in under 30 seconds.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_GOAL = ROOT / "data" / "traces" / "demo_allreduce_16r_1MiB.goal"
DEFAULT_OUT = ROOT / "data" / "demo_output"


def run(cmd):
    print(">>>", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", type=Path, default=DEFAULT_GOAL,
                    help=f"GOAL trace (default: {DEFAULT_GOAL.relative_to(ROOT)})")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--with-lp", action="store_true",
                    help="Also run the Composite-LP stage. Requires Gurobi "
                         "and first generates a LogGOPSim comm_dep sidecar. "
                         "The LP stage is off by default because real paper "
                         "runs are much larger than the demo trace.")
    args = ap.parse_args()

    if not args.goal.exists():
        print(f"error: {args.goal} not found", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== LogGOPSim replay (builds and runs LogGOPSim on the demo GOAL) ===")
    run([
        sys.executable, str(HERE / "run_lgs_sweep.py"),
        "--goal", str(args.goal),
        "--out", str(args.out_dir / "lgs_points.csv"),
        "--latencies", "0", "1000", "10000", "100000",
    ])

    if args.with_lp:
        comm_dep = args.out_dir / "comm_dep.csv"
        print("\n=== Generate comm_dep sidecar for LP ===")
        run([
            sys.executable, str(HERE / "run_lgs.py"),
            "--goal", str(args.goal),
            "--L", "1000", "--G", "0.04", "--o", "200",
            "--comm-dep-out", str(comm_dep),
        ])

        print("\n=== Composite-LP sweep ===")
        run([
            sys.executable, str(HERE / "run_composite_lp.py"),
            "--goal", str(args.goal),
            "--comm-dep", str(comm_dep),
            "--out", str(args.out_dir / "composed_runtime.csv"),
            "--l-min", "0", "--l-max", "1000000", "--step", "100000",
        ])

    print(f"\nDemo complete. Outputs in {args.out_dir.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
