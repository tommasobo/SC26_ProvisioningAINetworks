#!/usr/bin/env python3
"""Regenerate fixed-latency NCCL Composite-LP bandwidth sensitivity curves.

This is the end-to-end metadata Composite path used for the Llama N32
bandwidth panel: read V2 NCCL generator sidecars, rebuild each unique NCCL
collective motif as GOAL, convert it through the LP converter at a fixed
latency, and compose the rank program while sweeping inter-node bandwidth.

The script intentionally does not use the GOAL-level ``comm_dep.csv`` sidecar.
It needs ``collective_instances.csv`` and ``comm_ring_info.csv`` from the V2
generator plus the NPKit calibration JSON files.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gc
import hashlib
import json
import os
import resource
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "solver"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SOLVER) not in sys.path:
    sys.path.insert(0, str(SOLVER))

from llamp_nccl.cache import _signature_hash
from llamp_nccl.types import CollectiveSignature, NetworkParams
from pipeline.run_nccl_composite import (
    DEFAULT_GENERATOR,
    DEFAULT_NPKIT_LL,
    DEFAULT_NPKIT_SIMPLE,
    _build_signature,
    _build_topologies,
    _rank_count,
)


G_INTRA = 0.00333
L_INTRA = 350.0
O_COST = 200.0
DEFAULT_FIXED_L_NS = 4_000.0


@dataclass
class PreparedTrace:
    analysis_dir: Path
    records: list[dict[str, Any]]
    global_nranks: int | None
    comm_channel_topos: dict[str, Any]
    default_topos: dict[int, Any]
    ranks_per_node: int
    streams_in_trace: int
    max_active_collectives: int
    overlap_ns: float
    base_fixed_ns: float
    supported_collectives: int
    unsupported_collectives: int


def gbps_to_ns_per_byte(bw_gbps: float) -> float:
    if bw_gbps <= 0:
        raise ValueError("bandwidth must be positive")
    return 8.0 / bw_gbps


def fixed_l_cache_key(sig: CollectiveSignature, fixed_l_ns: float) -> str:
    raw = f"fixed_l_exact_goal_v2|{_signature_hash(sig)}|{fixed_l_ns:.3f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _prepend_sys_path(path: Path) -> None:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _solve_collective_runtime_at_l_exact_goal(
    sig: CollectiveSignature,
    extra_topos: list[Any],
    fixed_l_ns: float,
    generator_dir: str,
    npkit_simple: str,
    npkit_ll: str,
    enable_intra_node_transfer: bool | None,
    nic_per_rank: bool,
    nics_per_node: int,
) -> dict[str, Any]:
    import gurobipy as gp

    t0 = time.time()
    if extra_topos:
        object.__setattr__(sig, "extra_ring_topologies", extra_topos)

    _prepend_sys_path(Path(generator_dir))
    _prepend_sys_path(SOLVER)

    from dep_graph_generator import DependencyGraphGenerator
    from goal import GoalOpAtom, GoalRecv, GoalSend
    from lp_converter import LPConverter
    from nccl_comm import (
        AllGather as NCCLAllGather,
        AllReduce as NCCLAllReduce,
        CollAlgo,
        CollChnlInfo,
        CollInfo,
        Communicator,
        NCCLProto,
        ReduceScatter as NCCLReduceScatter,
    )
    from nccl_primitives import init_data

    try:
        from nccl_primitives import init_generation_flags
    except ImportError:
        init_generation_flags = None

    init_data(npkit_simple, npkit_ll)
    if init_generation_flags is not None and enable_intra_node_transfer is not None:
        init_generation_flags(False, False, enable_intra_node_transfer)

    topo = sig.ring_topology
    n_ranks = sig.n_ranks
    n_channels = sig.n_channels
    gpu_ids = [(f"node{topo.rank_to_node[r]}", r) for r in range(n_ranks)]
    comm = Communicator("bw_sensitivity_comm", gpu_ids)

    all_topos = [topo] + list(getattr(sig, "extra_ring_topologies", []) or [])
    while len(all_topos) < n_channels:
        all_topos.append(topo)
    for ch_topo in all_topos:
        for rank in range(n_ranks):
            nxt = ch_topo.ring_next[rank]
            prev = next(r for r in range(n_ranks) if ch_topo.ring_next[r] == rank)
            comm.add_ring_topo(rank, prev, nxt)

    coll_map = {
        "allreduce": NCCLAllReduce,
        "allgather": NCCLAllGather,
        "reducescatter": NCCLReduceScatter,
    }
    coll_class = coll_map.get(sig.collective_type)
    if coll_class is None:
        raise NotImplementedError(f"Unsupported collective: {sig.collective_type}")

    type_size = 1 if sig.collective_type == "allgather" else 4
    coll_info = CollInfo(
        root_rank=0,
        red_op=0,
        algo=CollAlgo.RING,
        proto=NCCLProto.SIMPLE,
        data_size=sig.data_bytes,
        type_size=type_size,
        chunk_steps=sig.slices_per_step * 2,
        slice_steps=2,
        step_size=sig.slice_bytes // 2,
    )

    work_count_per_ch = sig.data_bytes // (type_size * n_channels)
    chunk_count = sig.slice_bytes // type_size
    coll_chnl_infos = [
        CollChnlInfo(
            count=work_count_per_ch,
            chunk_count=chunk_count,
            work_count=work_count_per_ch,
            last_chunk_count=chunk_count,
            work_offset=ch * work_count_per_ch,
            send_buff=0,
            recv_buff=0,
        )
        for ch in range(n_channels)
    ]

    gpu_id2goal_rank = {gid: i for i, gid in enumerate(gpu_ids)}
    goal_lines = [f"num_ranks {n_ranks}\n"]
    for rank in range(n_ranks):
        GoalOpAtom.task_id_for_rank = {}
        GoalSend.send_message_id = {}
        GoalRecv.recv_message_id = {}

        coll = coll_class(gpu_ids[rank], comm, coll_info, coll_chnl_infos, context=1)
        primitives = coll.to_primitives()
        goal_op, _ = primitives.to_goal(gpu_id2goal_rank, 0, 0)
        rank_lines = list(goal_op.generate_lines())

        goal_lines.append(f"\nrank {rank} {{\n")
        for line in rank_lines:
            goal_lines.append(f"{line}\n")
        goal_lines.append("}\n")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".goal", delete=False) as handle:
        handle.writelines(goal_lines)
        goal_path = handle.name

    try:
        dep_graph = DependencyGraphGenerator(goal_path, None).generate(False)
        rank_node_map = {r: int(topo.rank_to_node[r]) for r in range(n_ranks)}
        model = LPConverter(
            dep_graph,
            o=int(sig.network.o),
            rank_node_map=rank_node_map,
            l_intra=sig.network.L_intra,
            g_intra=sig.network.G_intra,
            nic_per_rank=nic_per_rank,
            nics_per_node=nics_per_node,
        ).convert_to_lp(verbose=False, G=sig.network.G_inter)
        model.setParam("LogToConsole", 0)
        model.setParam("Method", 1)
        l_var = model.getVarByName("l")
        if l_var is None:
            raise RuntimeError("LP model does not contain latency variable 'l'")
        l_var.lb = fixed_l_ns
        l_var.ub = fixed_l_ns
        model.optimize()
        if model.Status != gp.GRB.OPTIMAL:
            raise RuntimeError(f"Gurobi failed with status {model.Status}")
        return {
            "runtime_ns": float(model.objVal),
            "lp_vars": int(model.NumVars),
            "lp_constrs": int(model.NumConstrs),
            "solve_time_s": float(time.time() - t0),
        }
    finally:
        os.unlink(goal_path)


def _solve_worker(payload: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
    (
        key,
        sig,
        extra_topos,
        fixed_l_ns,
        generator_dir,
        npkit_simple,
        npkit_ll,
        enable_intra_node_transfer,
        nic_per_rank,
        nics_per_node,
    ) = payload
    return key, _solve_collective_runtime_at_l_exact_goal(
        sig=sig,
        extra_topos=extra_topos,
        fixed_l_ns=fixed_l_ns,
        generator_dir=generator_dir,
        npkit_simple=npkit_simple,
        npkit_ll=npkit_ll,
        enable_intra_node_transfer=enable_intra_node_transfer,
        nic_per_rank=nic_per_rank,
        nics_per_node=nics_per_node,
    )


def _required(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _events_overlap(records: list[dict[str, Any]]) -> tuple[float, int]:
    events: list[tuple[float, int]] = []
    for row in records:
        events.append((float(row["start"]), 1))
        events.append((float(row["end"]), -1))
    events.sort(key=lambda item: (item[0], item[1]))

    overlap_ns = 0.0
    active = 0
    max_active = 0
    prev_t = None
    for t, delta in events:
        if prev_t is not None and active > 1:
            overlap_ns += max(0.0, t - prev_t)
        active += delta
        max_active = max(max_active, active)
        prev_t = t
    return overlap_ns, max_active


def prepare_trace(args: argparse.Namespace) -> PreparedTrace:
    analysis_dir = args.analysis_dir.resolve()
    ci_path = analysis_dir / "collective_instances.csv"
    ri_path = analysis_dir / "comm_ring_info.csv"
    _required(ci_path, "collective_instances.csv")
    _required(ri_path, "comm_ring_info.csv")

    ci = pd.read_csv(ci_path)
    ri = pd.read_csv(ri_path)
    global_nranks = _rank_count(ci, args.rank_count_mode, args.nranks)
    comm_channel_topos, default_topos = _build_topologies(
        ri,
        args.ranks_per_node,
        args.node_map_mode,
        args.ring_duplicate_policy,
    )

    rank_df = ci[ci["goal_rank"] == args.program_rank].sort_values("start").copy()
    if args.max_collectives is not None:
        rank_df = rank_df.head(args.max_collectives)
    if rank_df.empty:
        raise RuntimeError(f"no collectives found for goal_rank={args.program_rank}")

    records = rank_df.to_dict(orient="records")
    overlap_ns, max_active = _events_overlap(records)
    if overlap_ns > 0 and not args.force_sequential:
        raise RuntimeError(
            "fixed-L bandwidth composition currently supports non-overlapping "
            "rank timelines; rerun with --force-sequential to ignore stream overlap"
        )

    probe_net = NetworkParams(
        G_inter=args.G_inter_probe,
        G_intra=args.G_intra,
        L_intra=args.L_intra,
        o=args.o,
        msg_gap=args.msg_gap,
    )
    base_fixed_ns = 0.0
    supported = 0
    unsupported = 0
    prev_end = None
    for row in records:
        start = float(row["start"])
        end = float(row["end"])
        if prev_end is not None:
            gap = start - prev_end
            if gap > 0:
                base_fixed_ns += gap
        sig, _, _ = _build_signature(
            pd.Series(row),
            global_nranks,
            probe_net,
            comm_channel_topos,
            default_topos,
            args.ranks_per_node,
        )
        if sig is None:
            base_fixed_ns += end - start
            unsupported += 1
        else:
            supported += 1
        prev_end = end

    streams = int(rank_df["stream"].nunique()) if "stream" in rank_df.columns else 1
    return PreparedTrace(
        analysis_dir=analysis_dir,
        records=records,
        global_nranks=global_nranks,
        comm_channel_topos=comm_channel_topos,
        default_topos=default_topos,
        ranks_per_node=args.ranks_per_node,
        streams_in_trace=streams,
        max_active_collectives=max_active,
        overlap_ns=overlap_ns,
        base_fixed_ns=base_fixed_ns,
        supported_collectives=supported,
        unsupported_collectives=unsupported,
    )


def _unique_signatures_for_point(
    prepared: PreparedTrace,
    net: NetworkParams,
) -> tuple[dict[str, tuple[CollectiveSignature, list[Any]]], dict[str, int]]:
    unique: dict[str, tuple[CollectiveSignature, list[Any]]] = {}
    counts: dict[str, int] = {}
    for row in prepared.records:
        sig, _, _ = _build_signature(
            pd.Series(row),
            prepared.global_nranks,
            net,
            prepared.comm_channel_topos,
            prepared.default_topos,
            prepared.ranks_per_node,
        )
        if sig is None:
            continue
        key = _signature_hash(sig)
        if key not in unique:
            unique[key] = (sig, list(getattr(sig, "extra_ring_topologies", []) or []))
        counts[key] = counts.get(key, 0) + 1
    return unique, counts


def run_point(
    prepared: PreparedTrace,
    bw_gbps: float,
    args: argparse.Namespace,
    cache_dir: Path,
) -> dict[str, Any]:
    point_start = time.time()
    g_inter = gbps_to_ns_per_byte(bw_gbps)
    net = NetworkParams(
        G_inter=g_inter,
        G_intra=args.G_intra,
        L_intra=args.L_intra,
        o=args.o,
        msg_gap=args.msg_gap,
    )
    unique, counts = _unique_signatures_for_point(prepared, net)

    point_results: dict[str, dict[str, Any]] = {}
    uncached: list[tuple[Any, ...]] = []
    cache_hits = 0
    cache_dir.mkdir(parents=True, exist_ok=True)
    for key, (sig, extra_topos) in unique.items():
        cache_path = cache_dir / f"{fixed_l_cache_key(sig, args.fixed_l_ns)}.json"
        if cache_path.exists() and not args.no_cache:
            point_results[key] = json.loads(cache_path.read_text(encoding="utf-8"))
            cache_hits += 1
        else:
            uncached.append(
                (
                    key,
                    sig,
                    extra_topos,
                    float(args.fixed_l_ns),
                    str(args.generator_dir.resolve()),
                    str(args.npkit_simple.resolve()),
                    str(args.npkit_ll.resolve()),
                    args.enable_intra_node_transfer,
                    bool(args.nic_per_rank),
                    int(args.nics_per_node),
                )
            )

    solved_unique = 0
    unique_solve_time_s = 0.0
    if uncached:
        workers = min(args.max_workers, len(uncached))
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_payload = {
                executor.submit(_solve_worker, payload): payload
                for payload in uncached
            }
            for future in concurrent.futures.as_completed(future_to_payload):
                payload = future_to_payload[future]
                key, result = future.result()
                point_results[key] = result
                solved_unique += 1
                unique_solve_time_s += float(result["solve_time_s"])
                sig = payload[1]
                cache_path = cache_dir / f"{fixed_l_cache_key(sig, args.fixed_l_ns)}.json"
                if not args.no_cache:
                    cache_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    runtime_ns = prepared.base_fixed_ns
    for key, count in counts.items():
        runtime_ns += count * float(point_results[key]["runtime_ns"])

    lp_vars = sum(int(result["lp_vars"]) for result in point_results.values())
    lp_constrs = sum(int(result["lp_constrs"]) for result in point_results.values())
    return {
        "bw_gbps": float(bw_gbps),
        "G_inter_ns_per_byte": float(g_inter),
        "fixed_l_ns": float(args.fixed_l_ns),
        "runtime_ns": float(runtime_ns),
        "runtime_ms": float(runtime_ns / 1e6),
        "supported_collectives": int(prepared.supported_collectives),
        "unsupported_collectives": int(prepared.unsupported_collectives),
        "n_unique_sigs": int(len(unique)),
        "solved_unique_sigs": int(solved_unique),
        "cache_hits": int(cache_hits),
        "lp_vars": int(lp_vars),
        "lp_constrs": int(lp_constrs),
        "unique_solve_time_s": float(unique_solve_time_s),
        "wall_time_s": float(time.time() - point_start),
    }


def plot_sweep(df: pd.DataFrame, out_dir: Path, fixed_l_ns: float) -> dict[str, str]:
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 7.5,
        "lines.linewidth": 1.8,
        "figure.dpi": 300,
        "savefig.bbox": "tight",
    })
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.plot(df["bw_gbps"], df["runtime_ms"], color="#2166AC", marker="o", markersize=3.5)
    ax.axvline(200.0, color="gray", linestyle="--", linewidth=1.0, alpha=0.8, label="200 Gbps")
    ax.set_xscale("log")
    ax.set_xlabel("Inter-node Bandwidth [Gbps]")
    ax.set_ylabel(f"Composed Runtime at L={fixed_l_ns / 1000:.1f} us [ms]")
    ax.set_title("NCCL Composite-LP Bandwidth Sensitivity")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="upper right", framealpha=0.9, edgecolor="none")

    png_path = out_dir / "bandwidth_sensitivity.png"
    pdf_path = out_dir / "bandwidth_sensitivity.pdf"
    fig.tight_layout()
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    return {"png": str(png_path), "pdf": str(pdf_path)}


def _bandwidth_points(args: argparse.Namespace) -> list[float]:
    if args.bandwidths:
        return [float(v) for v in args.bandwidths]
    if args.num_points <= 0:
        raise ValueError("--num-points must be positive")
    if args.spacing == "log":
        return [float(x) for x in np.geomspace(args.min_bw_gbps, args.max_bw_gbps, args.num_points)]
    return [float(x) for x in np.linspace(args.min_bw_gbps, args.max_bw_gbps, args.num_points)]


def run(args: argparse.Namespace) -> int:
    _required(args.generator_dir, "NCCL generator directory")
    _required(args.npkit_simple, "NPKit Simple summary")
    _required(args.npkit_ll, "NPKit LL summary")
    prepared = prepare_trace(args)
    bw_points = _bandwidth_points(args)

    out_csv = args.out.resolve()
    out_dir = out_csv.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.cache_dir.resolve() if args.cache_dir else out_dir / "fixed_l_cache"
    if args.clear_cache and cache_dir.exists():
        shutil.rmtree(cache_dir)

    rows: list[dict[str, Any]] = []
    for idx, bw in enumerate(bw_points, start=1):
        print(
            f"[{idx}/{len(bw_points)}] BW={bw:.6g} Gbps "
            f"(G_inter={gbps_to_ns_per_byte(bw):.6f} ns/B, L={args.fixed_l_ns:.0f} ns)",
            flush=True,
        )
        row = run_point(prepared, bw, args, cache_dir)
        rows.append(row)
        print(
            f"    runtime={row['runtime_ms']:.3f} ms, solved={row['solved_unique_sigs']}, "
            f"cache_hits={row['cache_hits']}, wall={row['wall_time_s']:.1f}s",
            flush=True,
        )
        gc.collect()

    df = pd.DataFrame(rows).sort_values("bw_gbps")
    df.to_csv(out_csv, index=False)
    plot_paths = {} if args.no_plot else plot_sweep(df, out_dir, args.fixed_l_ns)

    summary = {
        "analysis_dir": str(prepared.analysis_dir),
        "out_csv": str(out_csv),
        "cache_dir": str(cache_dir),
        "generator_dir": str(args.generator_dir.resolve()),
        "npkit_simple": str(args.npkit_simple.resolve()),
        "npkit_ll": str(args.npkit_ll.resolve()),
        "fixed_inter_node_latency_ns": float(args.fixed_l_ns),
        "sweep": {
            "parameter": "inter_node_bandwidth_gbps",
            "min_bw_gbps": float(min(bw_points)),
            "max_bw_gbps": float(max(bw_points)),
            "num_points": int(len(bw_points)),
            "spacing": "explicit" if args.bandwidths else args.spacing,
            "bw_points_gbps": [float(x) for x in bw_points],
        },
        "trace": {
            "program_rank": int(args.program_rank),
            "rank_count_mode": args.rank_count_mode,
            "nranks_used": prepared.global_nranks,
            "ranks_per_node": int(args.ranks_per_node),
            "node_map_mode": args.node_map_mode,
            "ring_duplicate_policy": args.ring_duplicate_policy,
            "streams_in_trace": int(prepared.streams_in_trace),
            "max_active_collectives": int(prepared.max_active_collectives),
            "overlap_ms": float(prepared.overlap_ns / 1e6),
            "supported_collectives": int(prepared.supported_collectives),
            "unsupported_collectives": int(prepared.unsupported_collectives),
            "base_fixed_ms": float(prepared.base_fixed_ns / 1e6),
        },
        "network": {
            "G_intra_ns_per_byte": float(args.G_intra),
            "L_intra_ns": float(args.L_intra),
            "o_ns": float(args.o),
            "msg_gap_ns": float(args.msg_gap),
            "nic_per_rank": bool(args.nic_per_rank),
            "nics_per_node": int(args.nics_per_node),
            "enable_intra_node_transfer": args.enable_intra_node_transfer,
        },
        "runtime_range_ms": {
            "min": float(df["runtime_ms"].min()),
            "max": float(df["runtime_ms"].max()),
        },
        "artifacts": {
            "csv": str(out_csv),
            "plot_png": plot_paths.get("png"),
            "plot_pdf": plot_paths.get("pdf"),
        },
        "peak_rss_mb": float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"[nccl-bw] wrote {out_csv}")
    print(f"[nccl-bw] wrote {summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True, type=Path,
                        help="Directory containing collective_instances.csv and comm_ring_info.csv.")
    parser.add_argument("--out", required=True, type=Path,
                        help="Output bandwidth_sensitivity.csv path.")
    parser.add_argument("--cache-dir", type=Path,
                        help="Cache directory for fixed-L collective solves.")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Remove --cache-dir before solving.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Do not read or write fixed-L solve cache entries.")
    parser.add_argument("--generator-dir", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--npkit-simple", type=Path, default=DEFAULT_NPKIT_SIMPLE)
    parser.add_argument("--npkit-ll", type=Path, default=DEFAULT_NPKIT_LL)
    parser.add_argument("--program-rank", type=int, default=0)
    parser.add_argument("--max-collectives", type=int)
    parser.add_argument("--rank-count-mode", choices=("row-nranks", "first-row", "goal-ranks"),
                        default="row-nranks")
    parser.add_argument("--nranks", type=int)
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--node-map-mode", choices=("metadata", "rank-block"), default="metadata")
    parser.add_argument("--ring-duplicate-policy", choices=("first", "last"), default="first")
    parser.add_argument("--force-sequential", action="store_true",
                        help="Compose rank events in timestamp order even if streams overlap.")
    parser.add_argument("--nic-per-rank", action="store_true",
                        help="Use one serialized NIC queue per rank inside motif LPs.")
    parser.add_argument("--nics-per-node", type=int, default=1,
                        help="Physical NIC queues per node when --nic-per-rank is enabled.")
    parser.add_argument("--enable-intra-node-transfer", action=argparse.BooleanOptionalAction,
                        default=None,
                        help="Override NCCL generator intra-node transfer mode when supported.")
    parser.add_argument("--G-intra", type=float, default=G_INTRA)
    parser.add_argument("--L-intra", type=float, default=L_INTRA)
    parser.add_argument("--o", type=float, default=O_COST)
    parser.add_argument("--msg-gap", type=float, default=0.0)
    parser.add_argument("--G-inter-probe", type=float, default=0.04,
                        help="Temporary G_inter only used to classify supported collectives.")
    parser.add_argument("--fixed-l-ns", type=float, default=DEFAULT_FIXED_L_NS)
    parser.add_argument("--bandwidths", nargs="*", type=float,
                        help="Explicit bandwidth points in Gbps. Overrides min/max/num/spacing.")
    parser.add_argument("--min-bw-gbps", type=float, default=10.0)
    parser.add_argument("--max-bw-gbps", type=float, default=1600.0)
    parser.add_argument("--num-points", type=int, default=20)
    parser.add_argument("--spacing", choices=("log", "linear"), default="log")
    parser.add_argument("--max-workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    if args.ranks_per_node <= 0:
        parser.error("--ranks-per-node must be positive")
    if args.nics_per_node <= 0:
        parser.error("--nics-per-node must be positive")
    if args.nranks is not None and args.nranks <= 0:
        parser.error("--nranks must be positive")
    if args.max_workers <= 0:
        parser.error("--max-workers must be positive")
    if args.fixed_l_ns < 0:
        parser.error("--fixed-l-ns must be non-negative")
    if args.min_bw_gbps <= 0 or args.max_bw_gbps <= 0:
        parser.error("--min-bw-gbps and --max-bw-gbps must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
