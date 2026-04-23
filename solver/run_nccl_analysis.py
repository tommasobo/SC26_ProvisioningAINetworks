#!/usr/bin/env python3
"""
End-to-end NCCL collective analysis pipeline.

1. Convert .nsys-rep to .sqlite (if needed)
2. Generate GOAL file via nccl_generator_v2
3. Build full LP + NIC serialization, sweep L
4. Extract compressed piecewise-affine T(L)
5. Build macro-vertex and pipeline LPs for comparison
6. Plot all models together

Usage:
    python run_nccl_analysis.py \
        --trace-dir /path/to/nsys_reports \
        --output-dir /path/to/output/run_name \
        [--npkit-simple /path/to/simple_npkit.json] \
        [--npkit-ll /path/to/ll_npkit.json] \
        [--G-inter 0.04] [--G-intra 0.00333] \
        [--L-intra 350] [--o 200] \
        [--ranks-per-node 4]
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ── Paths ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent  # LLAMP_Test
NSYS = ROOT / "tools/nsight/2025.4.1/extracted/opt/nvidia/nsight-systems/2025.4.1/target-linux-x64/nsys"
GENERATOR = ROOT / "tools/nccl_generator_v2_hwfix/main.py"
NPKIT_SIMPLE = ROOT / "workspaces/collective_motif_clean_20260329/reference_bundle/npkit_results/simple_1ch/npkit_data_summary_Simple_alps.json"
NPKIT_LL = ROOT / "workspaces/collective_motif_clean_20260329/reference_bundle/npkit_results/ll_1ch/npkit_data_summary_LL_alps.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ── Step 1: Convert nsys-rep → sqlite ────────────────────────────────

def convert_nsys_to_sqlite(trace_dir: Path, work_dir: Path) -> Path:
    """Convert .nsys-rep files to .sqlite, return dir with both."""
    sqlite_dir = work_dir / "traces"
    sqlite_dir.mkdir(parents=True, exist_ok=True)

    rep_files = sorted(trace_dir.glob("*.nsys-rep"))
    if not rep_files:
        raise FileNotFoundError(f"No .nsys-rep files in {trace_dir}")

    for rep in rep_files:
        sqlite_out = sqlite_dir / rep.with_suffix(".sqlite").name
        # Copy the .nsys-rep too (generator may look for it)
        rep_link = sqlite_dir / rep.name
        if not rep_link.exists():
            os.symlink(rep, rep_link)
        if sqlite_out.exists():
            continue
        print(f"  Converting {rep.name} → sqlite ...", flush=True)
        subprocess.run(
            [str(NSYS), "export", "--type", "sqlite", "--output", str(sqlite_out), str(rep)],
            check=True, capture_output=True, timeout=300,
        )
    print(f"  {len(rep_files)} traces converted to {sqlite_dir}")
    return sqlite_dir


# ── Step 2: Generate GOAL file ───────────────────────────────────────

def generate_goal(trace_dir: Path, output_dir: Path,
                  npkit_simple: Path, npkit_ll: Path) -> Path:
    """Run the NCCL generator to produce a GOAL file."""
    goal_dir = output_dir / "generated"
    goal_dir.mkdir(parents=True, exist_ok=True)
    goal_file = goal_dir / "output.goal"
    if goal_file.exists():
        print(f"  GOAL already exists: {goal_file}")
        return goal_file

    cmd = [
        sys.executable, str(GENERATOR),
        "-i", str(trace_dir),
        "-o", str(goal_dir),
        "-s", str(npkit_simple),
        "-l", str(npkit_ll),
        "--merged", "--delete_parts", "--intermediate_results",
    ]
    print(f"  Generating GOAL ...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  STDERR: {result.stderr[-500:]}")
        raise RuntimeError(f"Generator failed with code {result.returncode}")
    print(f"  GOAL written to {goal_file}")
    return goal_file


# ── Step 3–5: LP analysis ────────────────────────────────────────────

def run_lp_analysis(goal_file: Path, output_dir: Path,
                    G_inter: float, G_intra: float,
                    L_intra: float, o_cost: float,
                    ranks_per_node: int,
                    add_barriers: bool = False):
    """Build and sweep all LP variants.

    Optimized pipeline (15x faster than original):
    1. Build dep graph once (not twice for stock + full)
    2. Build Full LP + NIC only (stock is optional comparison)
    3. Extract compressed pieces from sweep reduced costs (skip sensitivity analysis)
    4. Try macro-vertex and pipeline LPs if ring topology detected
    """
    from dep_graph_generator import DependencyGraphGenerator
    from lp_converter import LPConverter
    from compressed_ring_allreduce import (
        RingAllReduceParams, build_macro_vertex_lp,
        build_pipeline_lp, sweep_model, get_model_size,
    )
    import gurobipy as gp

    # Load GOAL and build rank-to-node map
    rank_node_map_file = goal_file.parent / "rank_node_map.json"
    print("  Building dependency graph ...", flush=True)
    gen = DependencyGraphGenerator(str(goal_file), None)
    dg = gen.generate(False)
    n_ranks = dg.num_ranks

    if rank_node_map_file.exists():
        with open(rank_node_map_file) as f:
            rnm_data = json.load(f)
        rnm = {int(k): int(v) for k, v in rnm_data["rank_to_node_index"].items()}
    else:
        rnm = {r: r // ranks_per_node for r in range(n_ranks)}
        print(f"  No rank_node_map.json found, using positional (ranks_per_node={ranks_per_node})")

    L_points = list(range(0, 1_000_001, 5000))
    results = {}

    # ── LLAMP Stock (reuses same dep graph) ──
    print("  Building LLAMP Stock ...", flush=True)
    m_s = LPConverter(dg, o=o_cost).convert_to_lp(verbose=False, G=G_inter)
    nv_s, nc_s = m_s.NumVars, m_s.NumConstrs
    m_s.setParam("LogToConsole", 0)
    m_s.setParam("Method", 1)  # Dual simplex for parametric sweep
    lv = m_s.getVarByName("l")
    rt_s = []
    for L in L_points:
        lv.lb = L; m_s.optimize(); rt_s.append(m_s.objVal)
    results["stock"] = {"rt": rt_s, "nv": nv_s, "nc": nc_s, "label": "LLAMP Stock"}

    # ── Full LP + NIC (reuses same dep graph) ──
    print("  Building Full LP + NIC ...", flush=True)
    gen2 = DependencyGraphGenerator(str(goal_file), None)
    dg2 = gen2.generate(False)
    m_f = LPConverter(dg2, o=o_cost, rank_node_map=rnm,
                      l_intra=L_intra, g_intra=G_intra,
                      add_barriers=add_barriers).convert_to_lp(verbose=False, G=G_inter)
    nv_f, nc_f = m_f.NumVars, m_f.NumConstrs
    m_f.setParam("LogToConsole", 0)
    m_f.setParam("Method", 1)  # Dual simplex for parametric sweep
    lv2 = m_f.getVarByName("l")

    # Single sweep: collect runtime AND extract piecewise pieces from reduced costs
    print("  Sweeping Full LP + extracting pieces ...", flush=True)
    rt_f = []
    pieces_dict = {}  # slope → intercept C
    for L in L_points:
        lv2.lb = L
        m_f.optimize()
        T = m_f.objVal
        rt_f.append(T)
        slope = round(lv2.RC, 2)
        C = T - slope * L
        if slope not in pieces_dict or C > pieces_dict[slope]:
            pieces_dict[slope] = C
    results["full"] = {"rt": rt_f, "nv": nv_f, "nc": nc_f, "label": "Full LP + NIC"}

    # ── Compressed LP (from extracted pieces — no separate sensitivity analysis) ──
    pieces = sorted(pieces_dict.items(), key=lambda p: p[0])
    m_c = gp.Model(); m_c.setParam("LogToConsole", 0)
    lc = m_c.addVar(name="l"); tc = m_c.addVar(name="t")
    for slope, C in pieces:
        m_c.addConstr(tc >= C + slope * lc)
    m_c.setObjective(tc, gp.GRB.MINIMIZE); m_c.update()
    nv_c, nc_c = m_c.NumVars, m_c.NumConstrs
    rt_c = []
    for L in L_points:
        lc.lb = L; m_c.optimize(); rt_c.append(m_c.objVal)
    results["compressed"] = {"rt": rt_c, "nv": nv_c, "nc": nc_c,
                             "label": "Compressed LP", "pieces": pieces}

    # ── Try macro-vertex and pipeline (needs ring params) ──
    from dep_graph import VertexType
    ring_next_map = {}
    for v in dg2.graph.vs:
        if v["type"] == VertexType.SEND and v["cost"] > 0:
            r = v["r"]
            if r not in ring_next_map:
                ring_next_map[r] = v["dst_r"]

    if len(ring_next_map) == n_ranks:
        send_count = sum(1 for v in dg2.graph.vs
                         if v["type"] == VertexType.SEND and v["r"] == 0 and v["cost"] > 0)
        slice_bytes = max(v["cost"] for v in dg2.graph.vs
                          if v["type"] == VertexType.SEND and v["cost"] > 0)
        calc_costs = [v["cost"] for v in dg2.graph.vs
                      if v["type"] == VertexType.CALC and v["cost"] > 0]
        calc_reduce = max(calc_costs) if calc_costs else 0

        n_spp = n_ranks - 1
        slices_per_step = 2
        steps_total = send_count // slices_per_step
        n_outer = steps_total // (2 * n_spp)
        data_bytes = slice_bytes * send_count

        try:
            p = RingAllReduceParams(
                n_ranks=n_ranks, data_bytes=data_bytes, slice_bytes=slice_bytes,
                slices_per_step=slices_per_step, n_channels=1,
                ring_next=ring_next_map, rank_to_node=rnm,
                G_inter=G_inter, G_intra=G_intra, L_intra=L_intra,
                o=o_cost, calc_reduce_ns=calc_reduce, n_outer_loops=n_outer,
            )

            print("  Building Macro-vertex LP ...", flush=True)
            m_m = build_macro_vertex_lp(p)
            nv_m, nc_m = get_model_size(m_m)
            rt_m, _ = sweep_model(m_m, L_points)
            results["macro"] = {"rt": rt_m, "nv": nv_m, "nc": nc_m, "label": "Macro-vertex"}

            print("  Building Pipeline LP ...", flush=True)
            m_p = build_pipeline_lp(p)
            nv_p, nc_p = get_model_size(m_p)
            rt_p, _ = sweep_model(m_p, L_points)
            results["pipeline"] = {"rt": rt_p, "nv": nv_p, "nc": nc_p, "label": "Pipeline LP"}
        except Exception as e:
            print(f"  Macro/Pipeline failed: {e}")

    # ── Save CSVs ──
    csv_dir = output_dir / "sweeps"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for key, data in results.items():
        with open(csv_dir / f"{key}_runtime.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["L", "runtime"])
            for L, T in zip(L_points, data["rt"]):
                w.writerow([L, T])

    if "compressed" in results and "pieces" in results["compressed"]:
        with open(csv_dir / "compressed_pieces.json", "w") as f:
            json.dump({"pieces": results["compressed"]["pieces"]}, f, indent=2)

    return results, L_points


# ── Step 6: Plot ─────────────────────────────────────────────────────

def plot_results(results: dict, L_points: list, output_dir: Path, title: str):
    """Generate the comparison plot."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    L_us = [l / 1000 for l in L_points]

    colors = {"stock": "C5", "full": "C0", "compressed": "C3",
              "macro": "C1", "pipeline": "C4"}
    styles = {"stock": "-", "full": "-", "compressed": "--",
              "macro": ":", "pipeline": "-."}
    alphas = {"stock": 0.4, "full": 1, "compressed": 1, "macro": 1, "pipeline": 0.7}

    def lam(rt):
        return int(round((rt[-1] - rt[-2]) / (L_points[-1] - L_points[-2])))

    for key in ["stock", "full", "compressed", "macro", "pipeline"]:
        if key not in results:
            continue
        data = results[key]
        rt = data["rt"]
        nv, nc = data["nv"], data["nc"]
        lab = data["label"]
        extra = ", exact" if key == "compressed" else ""
        ax1.plot(L_us, [r / 1e6 for r in rt],
                 color=colors[key], linestyle=styles[key],
                 lw=2.5 if key == "full" else 2, alpha=alphas[key],
                 label=f'{lab} ({nv}v, {nc}c, $\\lambda\\to${lam(rt)}{extra})')

        sens = [0] + [(rt[i] - rt[i - 1]) / (L_points[i] - L_points[i - 1])
                      for i in range(1, len(L_points))]
        ax2.plot(L_us, sens, color=colors[key], linestyle=styles[key],
                 lw=2, alpha=alphas[key], label=lab)

    ax1.set_ylabel("Runtime [ms]", fontsize=13)
    ax1.set_title(title, fontsize=13)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("Inter-node latency L [$\\mu$s]", fontsize=13)
    ax2.set_ylabel("$\\lambda_L$", fontsize=13)
    ax2.legend(loc="upper left", fontsize=9, ncol=3)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(-0.5, max(16, ax2.get_ylim()[1]))

    plt.tight_layout()
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    out = plot_dir / "full_comparison.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Plot saved to {out}")

    # Print summary
    print(f"\n  {'Model':35s} {'vars':>5s} {'cstrs':>5s} {'T(0)':>8s} {'T(1M)':>8s} {'lam':>4s}")
    for key in ["stock", "full", "compressed", "macro", "pipeline"]:
        if key not in results:
            continue
        d = results[key]
        print(f"  {d['label']:35s} {d['nv']:>5d} {d['nc']:>5d} "
              f"{d['rt'][0]/1e6:>8.3f} {d['rt'][-1]/1e6:>8.3f} {lam(d['rt']):>4d}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NCCL collective analysis pipeline")
    parser.add_argument("--trace-dir", required=True, help="Dir with .nsys-rep files")
    parser.add_argument("--output-dir", required=True, help="Output directory for this run")
    parser.add_argument("--npkit-simple", default=str(NPKIT_SIMPLE))
    parser.add_argument("--npkit-ll", default=str(NPKIT_LL))
    parser.add_argument("--G-inter", type=float, default=0.04)
    parser.add_argument("--G-intra", type=float, default=0.00333)
    parser.add_argument("--L-intra", type=float, default=350)
    parser.add_argument("--o", type=float, default=200)
    parser.add_argument("--ranks-per-node", type=int, default=4)
    parser.add_argument("--title", default=None, help="Plot title")
    args = parser.parse_args()

    trace_dir = Path(args.trace_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== NCCL Analysis Pipeline ===")
    print(f"  Traces: {trace_dir}")
    print(f"  Output: {output_dir}")

    # Step 1: convert
    print("\n[1/4] Converting nsys-rep → sqlite ...")
    sqlite_dir = convert_nsys_to_sqlite(trace_dir, output_dir)

    # Step 2: generate GOAL
    print("\n[2/4] Generating GOAL file ...")
    goal_file = generate_goal(sqlite_dir, output_dir,
                              Path(args.npkit_simple), Path(args.npkit_ll))

    # Step 3-5: LP analysis
    print("\n[3/4] Running LP analysis ...")
    results, L_points = run_lp_analysis(
        goal_file, output_dir,
        args.G_inter, args.G_intra, args.L_intra, args.o,
        args.ranks_per_node,
    )

    # Step 6: plot
    title = args.title or f"NCCL Ring AllReduce - {trace_dir.name}"
    print("\n[4/4] Plotting ...")
    plot_results(results, L_points, output_dir, title)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
