#!/usr/bin/env python3
"""Run local-safe artifact checks.

The default path checks the packaged-data figure workflow and syntax/help
surfaces without Gurobi, Nsight, large trace downloads, or high-memory runs.
Use --pipeline to additionally run the tiny LogGOPSim demo.
"""

import argparse
import importlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd, timeout):
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    print(">>>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(
        [str(c) for c in cmd],
        cwd=ROOT,
        env=env,
        timeout=timeout,
        check=True,
    )


def require_files():
    required = [
        "README.md",
        "requirements.txt",
        "reproduce_all.py",
        "data/traces/demo_allreduce_16r_1MiB.goal",
        "data/output/grok_final/grok_N1024_latency_sweep.csv",
        "data/output/grok_final/grok_N1024_bw_sweep.csv",
        "data/output/vllm_llama8b_128tok/latency_runtime.csv",
        "pipeline/demo.py",
        "pipeline/generate_comm_dep_from_goal.py",
        "pipeline/regenerate_from_inputs.py",
        "pipeline/run_lgs.py",
        "pipeline/run_lgs_sweep.py",
        "pipeline/run_monolithic_lp.py",
        "pipeline/run_monolithic_points.py",
        "pipeline/run_nccl_generator.py",
        "pipeline/reproduce_fig5_from_nsys.sh",
        "scripts/compare_csv.py",
        "scripts/grok_node_scaling.py",
        "tools/LogGOPSim/Makefile",
        "tools/nccl_generator/main.py",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit("missing required artifact files: " + ", ".join(missing))


def require_default_modules():
    for module in ("matplotlib", "numpy", "pandas"):
        importlib.import_module(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-figure", action="store_true",
                        help="Skip the single packaged-figure smoke run.")
    parser.add_argument("--pipeline", action="store_true",
                        help="Also run the tiny LogGOPSim demo.")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout per subprocess in seconds.")
    args = parser.parse_args()

    require_files()
    require_default_modules()

    run([sys.executable, "reproduce_all.py", "--list"], args.timeout)
    run([sys.executable, "pipeline/generate_comm_dep_from_goal.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/regenerate_from_inputs.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/run_lgs.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/run_lgs_sweep.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/run_monolithic_lp.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/run_monolithic_points.py", "--help"], args.timeout)
    run([sys.executable, "pipeline/run_nccl_generator.py", "--help"], args.timeout)
    run([sys.executable, "scripts/compare_csv.py", "--help"], args.timeout)
    run([sys.executable, "scripts/grok_node_scaling.py", "--help"], args.timeout)
    run(["bash", "-n", "pipeline/reproduce_fig5_from_nsys.sh"], args.timeout)
    run(["bash", "pipeline/reproduce_fig5_from_nsys.sh", "--dry-run"], args.timeout)
    run([
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "pipeline",
        "tools/nccl_generator",
        "solver/llamp_nccl",
    ], args.timeout)

    if not args.skip_figure:
        run([sys.executable, "reproduce_all.py", "--only", "7"], args.timeout)

    if args.pipeline:
        run([sys.executable, "reproduce_all.py", "--pipeline", "--only", "3"], args.timeout)

    print("Artifact check passed.")


if __name__ == "__main__":
    main()
