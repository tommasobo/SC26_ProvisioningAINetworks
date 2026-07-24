#!/usr/bin/env python3
"""Solve one Monolithic LP at selected inter-node bandwidth-gap values."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solver"))


def rank_node_map(ranks_per_node: int, num_ranks: int) -> dict[int, int]:
    return {rank: rank // ranks_per_node for rank in range(num_ranks)}


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["G", "bw_gbps", "fixed_L_ns", "runtime", "status", "solve_s"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True, type=Path)
    parser.add_argument("--comm-dep", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--gaps", required=True, nargs="+", type=float,
                        help="Inter-node G values in ns/byte.")
    parser.add_argument("--fixed-L", type=float, default=3700)
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--l-intra", type=float, default=350)
    parser.add_argument("--g-intra", type=float, default=0.00333)
    parser.add_argument("--o", type=float, default=200)
    parser.add_argument("--add-barriers", action="store_true")
    parser.add_argument("--nic-per-rank", action="store_true")
    parser.add_argument("--nics-per-node", type=int, default=1)
    parser.add_argument("--method", type=int, choices=[-1, 0, 1, 2, 3, 4, 5], default=1)
    parser.add_argument("--threads", type=int, default=0)
    args = parser.parse_args()

    args.goal = args.goal.resolve()
    args.comm_dep = args.comm_dep.resolve()
    args.out = args.out.resolve()
    for path in (args.goal, args.comm_dep):
        if not path.is_file():
            parser.error(f"input not found: {path}")
    if args.ranks_per_node < 1 or args.nics_per_node < 1:
        parser.error("rank/NIC counts must be positive")
    if any(gap < 0 for gap in args.gaps):
        parser.error("bandwidth gaps must be non-negative")

    try:
        import gurobipy as gp
        from dep_graph_generator import DependencyGraphGenerator
        from lp_converter import LPConverter
    except Exception as exc:
        print(f"error: failed to import Gurobi/solver modules: {exc}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    graph = DependencyGraphGenerator(str(args.goal), str(args.comm_dep)).generate(False)
    converter = LPConverter(
        graph,
        o=args.o,
        rank_node_map=rank_node_map(args.ranks_per_node, graph.num_ranks),
        l_intra=args.l_intra,
        g_intra=args.g_intra,
        add_barriers=args.add_barriers,
        nic_per_rank=args.nic_per_rank,
        nics_per_node=args.nics_per_node,
    )
    # G=None keeps one scalar inter-node g variable in the model, allowing
    # warm-started sweeps without rebuilding the graph or LP.
    model = converter.convert_to_lp(verbose=False, G=None)
    model.setParam("LogToConsole", 0)
    model.setParam("Method", args.method)
    model.setParam("Threads", args.threads)
    l_var = model.getVarByName("l")
    g_var = model.getVarByName("g")
    if l_var is None or g_var is None:
        print("error: LP model lacks scalar l/g variables", file=sys.stderr)
        return 1
    l_var.lb = args.fixed_L
    l_var.ub = args.fixed_L

    rows: list[dict[str, Any]] = []
    for gap in args.gaps:
        g_var.lb = 0.0
        g_var.ub = gp.GRB.INFINITY
        g_var.lb = gap
        g_var.ub = gap
        solve_started = time.perf_counter()
        model.optimize()
        solve_s = time.perf_counter() - solve_started
        status = int(model.status)
        runtime = model.objVal if status == gp.GRB.OPTIMAL else ""
        rows.append({
            "G": gap,
            "bw_gbps": "" if gap == 0 else 8.0 / gap,
            "fixed_L_ns": args.fixed_L,
            "runtime": runtime,
            "status": status,
            "solve_s": solve_s,
        })
        print(f"[monolithic-bandwidth] G={gap:g} status={status} runtime_ns={runtime} solve_s={solve_s:.3f}", flush=True)
        write_rows(args.out, rows)

    metadata = {
        "goal": str(args.goal),
        "comm_dep": str(args.comm_dep),
        "gaps_ns_per_byte": args.gaps,
        "fixed_L_ns": args.fixed_L,
        "ranks_per_node": args.ranks_per_node,
        "l_intra_ns": args.l_intra,
        "g_intra_ns_per_byte": args.g_intra,
        "nic_per_rank": args.nic_per_rank,
        "nics_per_node": args.nics_per_node,
        "num_vertices": graph.num_vertices(),
        "num_edges": graph.num_edges(),
        "num_vars": model.NumVars,
        "num_constraints": model.NumConstrs,
        "wall_s": time.perf_counter() - started,
    }
    args.out.with_suffix(args.out.suffix + ".json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
