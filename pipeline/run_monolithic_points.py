#!/usr/bin/env python3
"""Solve a Monolithic-LP model at selected latency points.

This is a faster companion to ``pipeline/run_monolithic_lp.py`` for
data-level revalidation when only a few hardware-relevant latency points
are needed, for example a node-scaling plot at ``L=4000 ns``. It builds
one full dependency graph and one LP, then warm-starts Gurobi across the
requested ``--latencies``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "solver"
sys.path.insert(0, str(SOLVER))


def load_rank_node_map(path: Path | None, ranks_per_node: int | None, num_ranks: int) -> dict[int, int] | None:
    if path is not None:
        with path.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        if "rank_to_node_index" in data:
            data = data["rank_to_node_index"]
        return {int(k): int(v) for k, v in data.items()}
    if ranks_per_node is not None:
        return {rank: rank // ranks_per_node for rank in range(num_ranks)}
    return None


def validate_args(args: argparse.Namespace) -> int:
    args.goal = args.goal.resolve()
    args.out = args.out.resolve()
    args.comm_dep = args.comm_dep.resolve() if args.comm_dep is not None else None
    args.rank_node_map = args.rank_node_map.resolve() if args.rank_node_map is not None else None

    if not args.goal.exists():
        print(f"error: GOAL file not found: {args.goal}", file=sys.stderr)
        return 2
    if args.comm_dep is None and not args.allow_tag_match:
        print(
            "error: --comm-dep is required for real GOAL LP runs. "
            "Use --allow-tag-match only for known-simple synthetic traces.",
            file=sys.stderr,
        )
        return 2
    if args.comm_dep is not None:
        if not args.comm_dep.exists():
            print(f"error: comm_dep file not found: {args.comm_dep}", file=sys.stderr)
            return 2
        if args.comm_dep.stat().st_size == 0:
            print(f"error: comm_dep file is empty: {args.comm_dep}", file=sys.stderr)
            return 2
    if args.rank_node_map is not None and not args.rank_node_map.exists():
        print(f"error: rank-node-map file not found: {args.rank_node_map}", file=sys.stderr)
        return 2
    if args.rank_node_map is not None and args.ranks_per_node is not None:
        print("error: --rank-node-map and --ranks-per-node are mutually exclusive", file=sys.stderr)
        return 2
    if args.ranks_per_node is not None and args.ranks_per_node <= 0:
        print("error: --ranks-per-node must be positive", file=sys.stderr)
        return 2
    if args.nics_per_node <= 0:
        print("error: --nics-per-node must be positive", file=sys.stderr)
        return 2
    if not args.latencies:
        print("error: at least one --latencies value is required", file=sys.stderr)
        return 2
    return 0


def rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024**2
    except Exception:
        return None


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["L", "runtime", "status", "solve_s"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", required=True, type=Path, help="Input GOAL trace.")
    ap.add_argument("--comm-dep", type=Path, default=None,
                    help="LP comm_dep CSV sidecar produced by patched LogGOPSim.")
    ap.add_argument("--allow-tag-match", action="store_true",
                    help="Permit tag-only matching when --comm-dep is omitted. "
                         "Only safe for known-simple synthetic traces.")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output CSV with columns L,runtime,status.")
    ap.add_argument("--latencies", nargs="+", type=float, required=True,
                    help="Network latency points in ns.")
    ap.add_argument("--rank-node-map", type=Path, default=None,
                    help="Optional JSON mapping ranks to node indices.")
    ap.add_argument("--ranks-per-node", type=int, default=None,
                    help="Build a positional rank-to-node map.")
    ap.add_argument("--l-intra", type=float, default=350,
                    help="Fixed intra-node latency in ns (default: 350).")
    ap.add_argument("--g-intra", type=float, default=None,
                    help="Fixed intra-node bandwidth parameter in ns/byte.")
    ap.add_argument("--o", type=float, default=200,
                    help="LogGP overhead parameter in ns (default: 200).")
    ap.add_argument("--G", type=float, default=0.04,
                    help="Inter-node LogGP bandwidth parameter in ns/byte (default: 0.04).")
    ap.add_argument("--add-barriers", action="store_true",
                    help="Add inferred inter-collective barrier constraints.")
    ap.add_argument("--nic-per-rank", action="store_true",
                    help="Use one serialized NIC injection queue per rank.")
    ap.add_argument("--nics-per-node", type=int, default=1,
                    help="Number of physical NICs per node for --nic-per-rank.")
    ap.add_argument("--method", type=int, choices=[-1, 0, 1, 2, 3, 4, 5], default=1,
                    help="Gurobi LP method (default: 1, dual simplex).")
    ap.add_argument("--threads", type=int, default=0,
                    help="Gurobi thread limit; 0 uses the solver default.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate arguments and print the planned configuration.")
    args = ap.parse_args()

    err = validate_args(args)
    if err:
        return err

    print("[monolithic-points] goal:", args.goal)
    if args.comm_dep is not None:
        print("[monolithic-points] comm_dep:", args.comm_dep)
    print("[monolithic-points] latencies:", ", ".join(str(x) for x in args.latencies))
    if args.dry_run:
        print("[monolithic-points] dry run complete; solver was not launched.")
        return 0

    try:
        import gurobipy as gp
        from dep_graph_generator import DependencyGraphGenerator
        from lp_converter import LPConverter
    except Exception as exc:
        print(f"error: failed to import Gurobi/solver modules: {exc}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    gen = DependencyGraphGenerator(str(args.goal), str(args.comm_dep) if args.comm_dep else None)
    dep_graph = gen.generate(False)
    graph_s = time.perf_counter() - t0
    print(
        "[monolithic-points] graph vertices="
        f"{dep_graph.num_vertices()} edges={dep_graph.num_edges()} ranks={dep_graph.num_ranks} "
        f"built_in={graph_s:.1f}s rss_mb={rss_mb()}",
        flush=True,
    )

    rank_node_map = load_rank_node_map(args.rank_node_map, args.ranks_per_node, dep_graph.num_ranks)
    converter = LPConverter(
        dep_graph,
        o=args.o,
        rank_node_map=rank_node_map,
        l_intra=args.l_intra,
        g_intra=args.g_intra,
        add_barriers=args.add_barriers,
        nic_per_rank=args.nic_per_rank,
        nics_per_node=args.nics_per_node,
    )
    model = converter.convert_to_lp(verbose=False, G=args.G)
    model.setParam("LogToConsole", 0)
    model.setParam("Method", args.method)
    model.setParam("Threads", args.threads)
    l_var = model.getVarByName("l")
    if l_var is None:
        print("error: LP model does not contain latency variable 'l'", file=sys.stderr)
        return 1
    build_s = time.perf_counter() - t0
    print(
        "[monolithic-points] model vars="
        f"{model.NumVars} constraints={model.NumConstrs} built_in={build_s:.1f}s rss_mb={rss_mb()}",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    for latency in args.latencies:
        solve_t0 = time.perf_counter()
        l_var.lb = latency
        model.optimize()
        solve_s = time.perf_counter() - solve_t0
        status = int(model.status)
        runtime = model.objVal if status == gp.GRB.OPTIMAL else ""
        print(
            f"[monolithic-points] L={latency:g} status={status} "
            f"runtime_ns={runtime} solve_s={solve_s:.2f}",
            flush=True,
        )
        rows.append({
            "L": latency,
            "runtime": runtime,
            "status": status,
            "solve_s": solve_s,
        })
        write_rows(args.out, rows)

    metadata = {
        "goal": str(args.goal),
        "comm_dep": str(args.comm_dep) if args.comm_dep else None,
        "latencies_ns": args.latencies,
        "rank_node_map": str(args.rank_node_map) if args.rank_node_map else None,
        "ranks_per_node": args.ranks_per_node,
        "l_intra": args.l_intra,
        "g_intra": args.g_intra,
        "G": args.G,
        "o": args.o,
        "add_barriers": args.add_barriers,
        "nic_per_rank": args.nic_per_rank,
        "nics_per_node": args.nics_per_node,
        "method": args.method,
        "threads": args.threads,
        "num_vertices": dep_graph.num_vertices(),
        "num_edges": dep_graph.num_edges(),
        "num_ranks": dep_graph.num_ranks,
        "num_vars": model.NumVars,
        "num_constraints": model.NumConstrs,
        "wall_s": time.perf_counter() - t0,
        "rss_mb": rss_mb(),
    }
    stats_path = args.out.with_suffix(args.out.suffix + ".json")
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    print(f"[monolithic-points] wrote {args.out}")
    print(f"[monolithic-points] wrote {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
