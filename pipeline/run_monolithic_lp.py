#!/usr/bin/env python3
"""
Pipeline stage: GOAL trace -> Monolithic-LP latency sensitivity CSV.

Thin wrapper around ``solver/main.py -a sensitivity``. Builds a single
full-trace LP and sweeps the latency parameter via dual-simplex
warm-starts, producing the ``full_runtime.csv`` that serves as the
paper's Monolithic-LP baseline in Figures 3, 4, and 5. Writes
(L [ns], runtime [ns]).

NOTE: The paper's headline ``Composite LP`` methodology (per-signature
parametric solve + program-level composition via ``solver/llamp_nccl/``)
is a *separate* code path in this repository. It is cheaper to solve
but requires workspace-aware orchestration beyond the scope of a
single wrapper; its precomputed outputs ship under ``data/output/``.
Reviewers who want to re-run the Composite LP at scale should use
the workspace drivers cited in the AD.

Usage:
    python3 pipeline/run_monolithic_lp.py \\
        --goal data/traces/demo_allreduce_16r_1MiB.goal \\
        --out data/demo/full_runtime.csv \\
        --l-min 0 --l-max 1000000 --step 50000
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOLVER = ROOT / "solver"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", required=True, type=Path,
                    help="Input GOAL trace (NCCL-generated, carries unique tags)")
    ap.add_argument("--comm-dep", type=Path, default=None,
                    help="Companion comm_dep CSV that disambiguates sends/recvs. "
                         "Generate it with pipeline/run_lgs.py --comm-dep-out. "
                         "Required for real NCCL traces unless --allow-tag-match "
                         "is set for a known-simple synthetic trace.")
    ap.add_argument("--allow-tag-match", action="store_true",
                    help="Permit solver fallback matching by (src,dst,tag,cpu) "
                         "when --comm-dep is omitted. This is only safe for "
                         "known-simple synthetic traces with unique tags.")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output CSV (L_ns,runtime_ms)")
    ap.add_argument("--l-min", type=int, default=0,
                    help="Minimum latency sweep point, ns (default: 0)")
    ap.add_argument("--l-max", type=int, default=1_000_000,
                    help="Maximum latency sweep point, ns (default: 1e6)")
    ap.add_argument("--step", type=int, default=50_000,
                    help="Sweep step, ns (default: 50000)")
    ap.add_argument("--l-intra", type=int, default=350,
                    help="Intra-node latency, ns (default: 350)")
    ap.add_argument("--g-intra", type=float, default=None,
                    help="Fixed intra-node bandwidth parameter, ns/byte. "
                         "Used only when a rank-to-node map is provided.")
    ap.add_argument("--rank-node-map", type=Path, default=None,
                    help="Optional JSON mapping ranks to node indices.")
    ap.add_argument("--ranks-per-node", type=int, default=None,
                    help="Build a positional rank-to-node map when no JSON "
                         "rank map is available. Rank r maps to "
                         "floor(r / ranks_per_node).")
    ap.add_argument("--add-barriers", action="store_true",
                    help="Add inferred inter-collective barrier constraints.")
    ap.add_argument("--nic-per-rank", action="store_true",
                    help="Use one serialized NIC injection queue per rank.")
    ap.add_argument("--nics-per-node", type=int, default=1,
                    help="Number of physical NICs per node for --nic-per-rank "
                         "(default: 1).")
    ap.add_argument("--o", type=int, default=200,
                    help="LogGP overhead parameter, ns (default: 200)")
    ap.add_argument("--G", type=float, default=0.018,
                    help="LogGP bandwidth parameter, ns/byte (default: 0.018)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate arguments and print the solver command "
                         "without launching Gurobi.")
    args = ap.parse_args()

    args.goal = args.goal.resolve()
    args.out = args.out.resolve()
    if args.comm_dep is not None:
        args.comm_dep = args.comm_dep.resolve()
    if args.rank_node_map is not None:
        args.rank_node_map = args.rank_node_map.resolve()

    if args.rank_node_map is not None and args.ranks_per_node is not None:
        print("error: --rank-node-map and --ranks-per-node are mutually exclusive", file=sys.stderr)
        return 2
    if args.ranks_per_node is not None and args.ranks_per_node <= 0:
        print("error: --ranks-per-node must be positive", file=sys.stderr)
        return 2
    if args.nics_per_node <= 0:
        print("error: --nics-per-node must be positive", file=sys.stderr)
        return 2

    if not args.goal.exists():
        print(f"error: GOAL file not found: {args.goal}", file=sys.stderr)
        return 2
    if args.rank_node_map is not None and not args.rank_node_map.exists():
        print(f"error: rank-node-map file not found: {args.rank_node_map}", file=sys.stderr)
        return 2
    if args.comm_dep is None and not args.allow_tag_match:
        print(
            "error: --comm-dep is required for real GOAL LP runs. "
            "Generate it with: python3 pipeline/run_lgs.py --goal "
            f"{args.goal} --L 1000 --G 0.04 --o 200 --comm-dep-out <comm_dep.csv>. "
            "Use --allow-tag-match only for known-simple synthetic traces.",
            file=sys.stderr,
        )
        return 2
    if args.comm_dep is not None:
        if not args.comm_dep.exists():
            print(f"error: comm_dep file not found: {args.comm_dep}", file=sys.stderr)
            return 2
        if args.comm_dep.stat().st_size == 0:
            print(
                f"error: comm_dep file is empty: {args.comm_dep}. "
                "Do not run LP with an empty sidecar; this usually means "
                "LogGOPSim did not record send/recv matches for that GOAL.",
                file=sys.stderr,
            )
            return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(SOLVER / "main.py"),
        "-g", str(args.goal),
        "-a", "sensitivity",
        "--l-min", str(args.l_min),
        "--l-max", str(args.l_max),
        "--step", str(args.step),
        "--l-intra", str(args.l_intra),
        "-o", str(args.o),
        "-G", str(args.G),
        "--output-dir", str(args.out.parent),
    ]
    if args.comm_dep is not None:
        cmd += ["-c", str(args.comm_dep)]
    if args.g_intra is not None:
        cmd += ["--g-intra", str(args.g_intra)]
    if args.rank_node_map is not None:
        cmd += ["--rank-node-map", str(args.rank_node_map)]
    if args.ranks_per_node is not None:
        cmd += ["--ranks-per-node", str(args.ranks_per_node)]
    if args.add_barriers:
        cmd += ["--add-barriers"]
    if args.nic_per_rank:
        cmd += ["--nic-per-rank"]
    if args.nics_per_node != 1:
        cmd += ["--nics-per-node", str(args.nics_per_node)]
    print("[monolithic-lp]", " ".join(cmd))
    if args.dry_run:
        print("[monolithic-lp] dry run complete; solver was not launched.")
        return 0
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=SOLVER)
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        print(f"[monolithic-lp] FAILED after {dt:.1f}s", file=sys.stderr)
        return r.returncode

    # The sensitivity action writes a fixed runtime filename.
    for produced in (args.out.parent / "tmp_runtime.csv",
                     args.out.parent / "runtime.csv",
                     args.out.parent / "net_lat_sen.csv"):
        if produced.exists() and produced.resolve() != args.out.resolve():
            produced.replace(args.out)
            break
    print(f"[monolithic-lp] wrote {args.out} ({dt:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
