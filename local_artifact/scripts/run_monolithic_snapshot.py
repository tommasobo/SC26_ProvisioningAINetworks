#!/usr/bin/env python3
"""Run the preserved April-5 monolithic LLAMP pipeline on an existing GOAL."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path("/home/tbonato/LLAMP_Test")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--add-barriers", action="store_true")
    parser.add_argument("--G-inter", type=float, default=0.04)
    parser.add_argument("--G-intra", type=float, default=0.00333)
    parser.add_argument("--L-intra", type=float, default=350)
    parser.add_argument("--o", type=float, default=200)
    parser.add_argument(
        "--solver-root",
        type=Path,
        default=ROOT / "workspaces/bandwidth_analysis/lgs-mpi/mpi-dep-graph",
    )
    args = parser.parse_args()

    solver_root = args.solver_root.resolve()
    sys.path.insert(0, str(solver_root))
    from run_nccl_analysis import run_lp_analysis

    args.out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    results, points = run_lp_analysis(
        args.goal,
        args.out,
        G_inter=args.G_inter,
        G_intra=args.G_intra,
        L_intra=args.L_intra,
        o_cost=args.o,
        ranks_per_node=args.ranks_per_node,
        add_barriers=args.add_barriers,
    )
    elapsed = time.perf_counter() - start

    summary = {
        "goal": str(args.goal.resolve()),
        "snapshot": str(solver_root),
        "elapsed_s": elapsed,
        "points": len(points),
        "add_barriers": args.add_barriers,
        "parameters": {
            "G_inter_ns_per_byte": args.G_inter,
            "G_intra_ns_per_byte": args.G_intra,
            "L_intra_ns": args.L_intra,
            "o_ns": args.o,
            "ranks_per_node": args.ranks_per_node,
        },
        "models": {},
    }
    for key, data in results.items():
        summary["models"][key] = {
            "variables": data["nv"],
            "constraints": data["nc"],
            "t0_ns": data["rt"][0],
            "tend_ns": data["rt"][-1],
        }
    (args.out / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
