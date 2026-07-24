#!/usr/bin/env python3
"""Run a monolithic fixed-latency bandwidth sweep on an existing GOAL."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--solver-root", required=True, type=Path)
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--fixed-L", type=float, default=5000)
    parser.add_argument("--G-max", type=float, default=0.12)
    parser.add_argument("--G-step", type=float, default=0.002)
    parser.add_argument("--G-intra", type=float, default=0.00333)
    parser.add_argument("--L-intra", type=float, default=350)
    parser.add_argument("--o", type=float, default=200)
    parser.add_argument("--add-barriers", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(args.solver_root.resolve()))
    from dep_graph_generator import DependencyGraphGenerator
    from lp_converter import LPConverter

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    dg = DependencyGraphGenerator(str(args.goal), None).generate(False)
    rank_map_path = args.goal.parent / "rank_node_map.json"
    if rank_map_path.exists():
        raw = json.loads(rank_map_path.read_text())
        raw = raw.get("rank_to_node_index", raw)
        rank_map = {int(k): int(v) for k, v in raw.items()}
        rank_map_source = str(rank_map_path)
    else:
        rank_map = {rank: rank // args.ranks_per_node for rank in range(dg.num_ranks)}
        rank_map_source = f"positional rank//{args.ranks_per_node}"

    model = LPConverter(
        dg,
        o=args.o,
        rank_node_map=rank_map,
        l_intra=args.L_intra,
        g_intra=args.G_intra,
        add_barriers=args.add_barriers,
    ).convert_to_lp(verbose=False, G=None)
    model.setParam("LogToConsole", 0)
    model.setParam("Method", 1)
    l_var = model.getVarByName("l")
    g_var = model.getVarByName("g")
    l_var.lb = args.fixed_L
    l_var.ub = args.fixed_L

    n_steps = int(round(args.G_max / args.G_step))
    points = [round(i * args.G_step, 12) for i in range(n_steps + 1)]
    rows = []
    pieces = {}
    for g_value in points:
        g_var.lb = g_value
        model.optimize()
        runtime = float(model.objVal)
        slope = round(float(g_var.RC), 2)
        intercept = runtime - slope * g_value
        rows.append({"G": g_value, "runtime": runtime})
        pieces[slope] = max(intercept, pieces.get(slope, float("-inf")))

    with (args.out / "bw_runtime.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["G", "runtime"])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "goal": str(args.goal.resolve()),
        "solver_root": str(args.solver_root.resolve()),
        "rank_map": rank_map_source,
        "fixed_L_ns": args.fixed_L,
        "G_intra_ns_per_byte": args.G_intra,
        "L_intra_ns": args.L_intra,
        "o_ns": args.o,
        "add_barriers": args.add_barriers,
        "points": len(points),
        "variables": model.NumVars,
        "constraints": model.NumConstrs,
        "elapsed_s": time.perf_counter() - started,
        "t_G0_ns": rows[0]["runtime"],
        "t_Gmax_ns": rows[-1]["runtime"],
        "pieces": sorted([[slope, intercept] for slope, intercept in pieces.items()]),
    }
    (args.out / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
