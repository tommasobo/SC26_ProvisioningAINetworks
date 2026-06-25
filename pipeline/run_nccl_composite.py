#!/usr/bin/env python3
"""Regenerate NCCL metadata-sidecar Composite-LP latency curves.

This is the Composite path used by the Grok/LLAMA paper workflow: it reads
NCCL generator metadata sidecars, solves unique collective motifs with
``solver/llamp_nccl``, and composes the rank-0 program into
``composed_runtime.csv``. It does not consume the monolithic LP
``comm_dep.csv`` sidecar.

Example:
    python3 pipeline/run_nccl_composite.py \\
        --analysis-dir /path/to/analysis \\
        --out results/composed_runtime.csv \\
        --parallel-solve --max-workers 8
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import shutil
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "solver"
DEFAULT_GENERATOR = ROOT / "tools" / "nccl_generator"
DEFAULT_NPKIT_SIMPLE = ROOT / "data" / "npkit" / "npkit_alps_simple.json"
DEFAULT_NPKIT_LL = ROOT / "data" / "npkit" / "npkit_alps_ll.json"

if str(SOLVER) not in sys.path:
    sys.path.insert(0, str(SOLVER))

from llamp_nccl.cache import CollectiveCache
from llamp_nccl.program import ProgramOp, analyze_parallel_streams, analyze_program
from llamp_nccl.solver import solve_collective
from llamp_nccl.types import CollectiveSignature, NetworkParams, RingTopology


def _latency_points(l_min: int, l_max: int, step: int) -> list[int]:
    if step <= 0:
        raise ValueError("--step must be positive")
    if l_max < l_min:
        raise ValueError("--l-max must be >= --l-min")
    return list(range(l_min, l_max + 1, step))


def _required(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _rank_count(ci: pd.DataFrame, mode: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if mode == "first-row":
        return int(ci["nranks"].iloc[0])
    if mode == "goal-ranks":
        return int(ci["goal_rank"].nunique())
    raise ValueError(f"unknown rank-count mode: {mode}")


def _build_topologies(
    ri: pd.DataFrame,
    nranks: int,
    ranks_per_node: int,
) -> tuple[dict[str, list[RingTopology]], RingTopology, dict[int, int]]:
    rank_to_node = {r: r // ranks_per_node for r in range(nranks)}
    comm_channel_topos: dict[str, list[RingTopology]] = {}
    for comm_id in ri["commId"].dropna().unique():
        ri_comm = ri[ri["commId"] == comm_id]
        topos: list[RingTopology] = []
        for channel in sorted(ri_comm["channelId"].dropna().unique()):
            ch_ring = ri_comm[ri_comm["channelId"] == channel]
            ring_next = {
                int(row["myRank"]): int(row["nextRank"])
                for _, row in ch_ring.iterrows()
            }
            if len(ring_next) == nranks and all(r in ring_next for r in range(nranks)):
                topos.append(RingTopology.from_dicts(nranks, ring_next, rank_to_node))
        if topos:
            comm_channel_topos[str(comm_id)] = topos

    default_topo = RingTopology.from_dicts(
        nranks,
        {r: (r + 1) % nranks for r in range(nranks)},
        rank_to_node,
    )
    return comm_channel_topos, default_topo, rank_to_node


def _series_value(row: pd.Series, name: str, default: Any) -> Any:
    value = row.get(name, default)
    return default if pd.isna(value) else value


def _build_signature(
    row: pd.Series,
    nranks: int,
    net: NetworkParams,
    comm_channel_topos: dict[str, list[RingTopology]],
    default_topo: RingTopology,
) -> tuple[CollectiveSignature | None, str, str]:
    collective_type = str(_series_value(row, "collective", "")).lower()
    data_bytes = int(_series_value(row, "data_size", 0))
    n_channels = int(_series_value(row, "channels", 1))
    algorithm = str(_series_value(row, "algo", "ring")).lower()
    protocol = str(_series_value(row, "proto", "simple")).lower()

    if data_bytes < 1024:
        return None, collective_type, "tiny"
    if algorithm == "tree":
        return None, collective_type, "tree"
    if collective_type not in {"allreduce", "allgather", "reducescatter"}:
        return None, collective_type, "unsupported_collective"
    if algorithm != "ring":
        return None, collective_type, "unsupported_algorithm"

    slice_steps = int(_series_value(row, "sliceSteps", 2))
    step_size = int(_series_value(row, "stepSize", 524288))
    chunk_steps = int(_series_value(row, "chunkSteps", 4))
    slice_bytes = slice_steps * step_size
    slices_per_step = max(1, chunk_steps // max(1, slice_steps))

    comm_id = str(_series_value(row, "commId", ""))
    coll_topos = comm_channel_topos.get(comm_id, [default_topo])
    topo0 = coll_topos[0]
    extra_topos = coll_topos[1:n_channels] if n_channels > 1 and len(coll_topos) > 1 else []

    sig = CollectiveSignature(
        collective_type=collective_type,
        algorithm="ring",
        protocol=protocol,
        data_bytes=data_bytes,
        n_ranks=nranks,
        n_channels=n_channels,
        slice_bytes=slice_bytes,
        slices_per_step=slices_per_step,
        n_outer_loops=1,
        calc_reduce_ns=0,
        ring_topology=topo0,
        network=net,
    )
    object.__setattr__(sig, "extra_ring_topologies", extra_topos)
    return sig, collective_type, "lp"


def _solve_worker(
    sig: CollectiveSignature,
    extra_topos: list[RingTopology],
    l_max: int,
) -> Any:
    if extra_topos:
        object.__setattr__(sig, "extra_ring_topologies", extra_topos)
    return solve_collective(sig, L_max=l_max)


def _write_curve(path: Path, l_points: list[int], runtimes: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=["L", "runtime"], lineterminator="\n")
        writer.writeheader()
        for latency, runtime in zip(l_points, runtimes):
            writer.writerow({"L": latency, "runtime": runtime})


def run_composite(args: argparse.Namespace) -> int:
    analysis_dir = args.analysis_dir.resolve()
    ci_path = analysis_dir / "collective_instances.csv"
    ri_path = analysis_dir / "comm_ring_info.csv"
    _required(ci_path, "collective_instances.csv")
    _required(ri_path, "comm_ring_info.csv")
    _required(args.generator_dir, "NCCL generator directory")
    _required(args.npkit_simple, "NPKit Simple summary")
    _required(args.npkit_ll, "NPKit LL summary")

    os.environ["LLAMP_NCCL_GENERATOR_DIR"] = str(args.generator_dir.resolve())
    os.environ["LLAMP_NPKIT_SIMPLE"] = str(args.npkit_simple.resolve())
    os.environ["LLAMP_NPKIT_LL"] = str(args.npkit_ll.resolve())
    if args.disable_intra_node_transfer:
        os.environ["LLAMP_NCCL_ENABLE_INTRA_NODE_TRANSFER"] = "0"

    out_csv = args.out.resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = args.cache_dir.resolve() if args.cache_dir else out_csv.parent.parent / "collective_cache"
    if args.clear_cache and cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache = CollectiveCache(path=cache_dir)

    t0 = time.perf_counter()
    ci = pd.read_csv(ci_path)
    ri = pd.read_csv(ri_path)
    nranks = _rank_count(ci, args.rank_count_mode, args.nranks)
    net = NetworkParams(
        G_inter=args.G_inter,
        G_intra=args.G_intra,
        L_intra=args.L_intra,
        o=args.o,
        msg_gap=args.msg_gap,
    )
    l_points = _latency_points(args.l_min, args.l_max, args.step)
    comm_channel_topos, default_topo, _ = _build_topologies(ri, nranks, args.ranks_per_node)

    r0 = ci[ci["goal_rank"] == args.program_rank].sort_values("start").copy()
    if args.max_collectives is not None:
        r0 = r0.head(args.max_collectives)
    if r0.empty:
        raise RuntimeError(f"no collectives found for goal_rank={args.program_rank}")

    unique_uncached: dict[str, tuple[CollectiveSignature, list[RingTopology]]] = {}
    signature_counts: dict[str, int] = {}
    fallback_rows: list[dict[str, Any]] = []
    for _, row in r0.iterrows():
        sig, collective_type, reason = _build_signature(row, nranks, net, comm_channel_topos, default_topo)
        if sig is None:
            fallback_rows.append({
                "collective": collective_type,
                "reason": reason,
                "data_size": int(_series_value(row, "data_size", 0)),
                "algo": str(_series_value(row, "algo", "")),
                "proto": str(_series_value(row, "proto", "")),
            })
            continue
        key = sig.short_description()
        signature_counts[key] = signature_counts.get(key, 0) + 1
        if key not in unique_uncached and not cache.has(sig):
            unique_uncached[key] = (sig, list(getattr(sig, "extra_ring_topologies", []) or []))

    solved = 0
    failed_signatures: dict[str, str] = {}
    if unique_uncached:
        if args.parallel_solve:
            workers = min(args.max_workers, len(unique_uncached))
            print(f"[nccl-composite] solving {len(unique_uncached)} uncached signatures with {workers} workers")
            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_to_key = {
                    executor.submit(_solve_worker, sig, extra, args.l_max): key
                    for key, (sig, extra) in unique_uncached.items()
                }
                for future in as_completed(future_to_key):
                    key = future_to_key[future]
                    try:
                        result = future.result()
                        cache.put(result)
                        solved += 1
                        print(
                            f"[nccl-composite] solved {solved}/{len(unique_uncached)} "
                            f"{key}: {result.piecewise.n_pieces} pieces, "
                            f"{result.lp_vars} vars"
                        )
                    except Exception as exc:
                        failed_signatures[key] = str(exc)
                        print(f"[nccl-composite] WARNING: {key} failed: {exc}", file=sys.stderr)
                        traceback.print_exc()
        else:
            print(f"[nccl-composite] solving {len(unique_uncached)} uncached signatures sequentially")
            for key, (sig, extra) in unique_uncached.items():
                try:
                    if extra:
                        object.__setattr__(sig, "extra_ring_topologies", extra)
                    result = solve_collective(sig, L_max=args.l_max)
                    cache.put(result)
                    solved += 1
                    print(
                        f"[nccl-composite] solved {solved}/{len(unique_uncached)} "
                        f"{key}: {result.piecewise.n_pieces} pieces, {result.lp_vars} vars"
                    )
                except Exception as exc:
                    failed_signatures[key] = str(exc)
                    print(f"[nccl-composite] WARNING: {key} failed: {exc}", file=sys.stderr)
                    traceback.print_exc()
    else:
        print("[nccl-composite] all signatures are already cached")

    def to_program_op(row: pd.Series, idx: int) -> ProgramOp:
        sig, collective_type, reason = _build_signature(row, nranks, net, comm_channel_topos, default_topo)
        if sig is None:
            return ProgramOp(
                name=f"{collective_type}_{reason}_{idx}",
                fixed_cost_ns=float(row["end"] - row["start"]),
            )
        cached = cache.get(sig)
        if cached is None:
            return ProgramOp(
                name=f"{collective_type}_failed_{idx}",
                fixed_cost_ns=float(row["end"] - row["start"]),
            )
        return ProgramOp(
            name=f"{collective_type}_{idx}",
            piecewise=cached.piecewise,
            nic_finish_ns=cached.nic_finish_ns,
            cpu_finish_ns=cached.cpu_finish_ns,
        )

    streams = int(r0["stream"].nunique()) if "stream" in r0.columns else 1
    if streams > 1 and not args.force_sequential:
        stream_ops: dict[str, list[ProgramOp]] = {}
        for stream_id in r0["stream"].dropna().unique():
            sr = r0[r0["stream"] == stream_id].sort_values("start")
            ops: list[ProgramOp] = []
            prev_end = None
            for idx, (_, row) in enumerate(sr.iterrows()):
                if prev_end is not None:
                    gap = float(row["start"]) - prev_end
                    if gap > 0:
                        ops.append(ProgramOp(name=f"gap_{idx}", fixed_cost_ns=gap))
                ops.append(to_program_op(row, idx))
                prev_end = float(row["end"])
            if ops:
                stream_ops[str(stream_id)] = ops
        _, program_pw = analyze_parallel_streams(stream_ops, l_points)
    else:
        ops: list[ProgramOp] = []
        prev_end = None
        for idx, (_, row) in enumerate(r0.iterrows()):
            if prev_end is not None:
                gap = float(row["start"]) - prev_end
                if gap > 0:
                    ops.append(ProgramOp(name=f"gap_{idx}", fixed_cost_ns=gap))
            ops.append(to_program_op(row, idx))
            prev_end = float(row["end"])
        _, program_pw = analyze_program(ops, l_points)

    runtimes = [program_pw.evaluate(latency) for latency in l_points]
    _write_curve(out_csv, l_points, runtimes)

    seen_keys: set[str] = set()
    total_vars = 0
    total_constrs = 0
    signature_rows: list[dict[str, Any]] = []
    for _, row in r0.iterrows():
        sig, _, reason = _build_signature(row, nranks, net, comm_channel_topos, default_topo)
        if sig is None:
            continue
        key = sig.short_description()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cached = cache.get(sig)
        status = "ok" if cached is not None else "failed"
        if cached is not None:
            total_vars += int(cached.lp_vars)
            total_constrs += int(cached.lp_constrs)
        signature_rows.append({
            "signature": key,
            "count": signature_counts.get(key, 0),
            "status": status,
            "reason": reason,
            "lp_vars": cached.lp_vars if cached is not None else "",
            "lp_constrs": cached.lp_constrs if cached is not None else "",
            "n_pieces": cached.piecewise.n_pieces if cached is not None else "",
            "error": failed_signatures.get(key, ""),
        })

    sig_csv = out_csv.parent / "signature_summary.csv"
    with sig_csv.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(
            out_f,
            fieldnames=[
                "signature", "count", "status", "reason",
                "lp_vars", "lp_constrs", "n_pieces", "error",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(signature_rows)

    fallback_csv = out_csv.parent / "fallback_collectives.csv"
    with fallback_csv.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(
            out_f,
            fieldnames=["collective", "reason", "data_size", "algo", "proto"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(fallback_rows)

    elapsed = time.perf_counter() - t0
    summary = {
        "analysis_dir": str(analysis_dir),
        "collective_instances": str(ci_path),
        "comm_ring_info": str(ri_path),
        "out_csv": str(out_csv),
        "cache_dir": str(cache_dir),
        "generator_dir": str(args.generator_dir.resolve()),
        "npkit_simple": str(args.npkit_simple.resolve()),
        "npkit_ll": str(args.npkit_ll.resolve()),
        "rank_count_mode": args.rank_count_mode,
        "nranks_used": nranks,
        "program_rank": args.program_rank,
        "ranks_per_node": args.ranks_per_node,
        "n_collectives": int(len(r0)),
        "n_streams": streams,
        "n_unique_lp_signatures": int(len(signature_rows)),
        "n_uncached_at_start": int(len(unique_uncached)),
        "n_solved": int(solved),
        "n_failed_signatures": int(len(failed_signatures)),
        "n_fallback_collectives": int(len(fallback_rows)),
        "lp_vars_unique_total": int(total_vars),
        "lp_constrs_unique_total": int(total_constrs),
        "l_min": args.l_min,
        "l_max": args.l_max,
        "step": args.step,
        "t0_ms": runtimes[0] / 1e6,
        "t_end_ms": runtimes[-1] / 1e6,
        "wall_time_s": elapsed,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "disable_intra_node_transfer": bool(args.disable_intra_node_transfer),
    }
    summary_path = out_csv.parent / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"[nccl-composite] wrote {out_csv}")
    print(f"[nccl-composite] wrote {summary_path}")
    return 1 if failed_signatures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True, type=Path,
                        help="Directory containing collective_instances.csv and comm_ring_info.csv.")
    parser.add_argument("--out", required=True, type=Path,
                        help="Output composed_runtime.csv path.")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="Cache directory for solved collective motifs.")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Remove --cache-dir before solving, forcing fresh motif LP regeneration.")
    parser.add_argument("--generator-dir", type=Path, default=DEFAULT_GENERATOR,
                        help="NCCL generator module directory used for motif GOAL generation.")
    parser.add_argument("--npkit-simple", type=Path, default=DEFAULT_NPKIT_SIMPLE)
    parser.add_argument("--npkit-ll", type=Path, default=DEFAULT_NPKIT_LL)
    parser.add_argument("--rank-count-mode", choices=("first-row", "goal-ranks"), default="first-row",
                        help="Rank count for motif signatures. first-row matches historical Grok scripts.")
    parser.add_argument("--nranks", type=int, default=None,
                        help="Explicit rank count override for motif signatures.")
    parser.add_argument("--program-rank", type=int, default=0,
                        help="GOAL rank whose collective timeline is composed.")
    parser.add_argument("--max-collectives", type=int, default=None,
                        help="Only compose the first N collectives for debugging.")
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--G-inter", type=float, default=0.04)
    parser.add_argument("--G-intra", type=float, default=0.00333)
    parser.add_argument("--L-intra", type=float, default=350)
    parser.add_argument("--o", type=float, default=200)
    parser.add_argument("--msg-gap", type=float, default=0)
    parser.add_argument("--l-min", type=int, default=0)
    parser.add_argument("--l-max", type=int, default=1_000_000)
    parser.add_argument("--step", type=int, default=5_000)
    parser.add_argument("--parallel-solve", action="store_true")
    parser.add_argument("--max-workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--force-sequential", action="store_true",
                        help="Ignore stream IDs and compose all rank operations as one sequence.")
    parser.add_argument("--disable-intra-node-transfer", action="store_true",
                        help="Use legacy 0-byte intra-node notifications plus calc costs in motif GOALs.")
    args = parser.parse_args()

    if args.nranks is not None and args.nranks <= 0:
        parser.error("--nranks must be positive")
    if args.ranks_per_node <= 0:
        parser.error("--ranks-per-node must be positive")
    if args.max_workers <= 0:
        parser.error("--max-workers must be positive")
    return run_composite(args)


if __name__ == "__main__":
    raise SystemExit(main())
