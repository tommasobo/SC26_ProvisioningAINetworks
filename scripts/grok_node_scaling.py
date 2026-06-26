#!/usr/bin/env python3
"""Aggregate Grok node-scaling data across HW, LGS, Monolithic LP, and Composite LP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def scratch_roots(args: argparse.Namespace) -> list[Path]:
    roots = [args.scratch_root]
    roots.extend(args.extra_scratch_root or [])
    deduped = []
    seen = set()
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def curve_columns(df: pd.DataFrame) -> tuple[str, str]:
    x_candidates = ["L", "L_ns", "latency_ns", "Latency"]
    y_candidates = ["runtime", "runtime_ns", "runtime_ns_mean", "Runtime"]
    x_col = next((col for col in x_candidates if col in df.columns), None)
    y_col = next((col for col in y_candidates if col in df.columns), None)
    if x_col is None or y_col is None:
        raise ValueError(f"could not infer latency/runtime columns from {list(df.columns)}")
    return x_col, y_col


def load_curve_ms(path: Path, target_latency: float) -> tuple[float | None, float | None, str]:
    df = pd.read_csv(path)
    x_col, y_col = curve_columns(df)
    xs = pd.to_numeric(df[x_col], errors="coerce").to_numpy(dtype=float)
    ys = pd.to_numeric(df[y_col], errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(xs) & np.isfinite(ys)
    xs = xs[mask]
    ys = ys[mask]
    if len(xs) == 0:
        return None, None, "empty_curve"
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    if np.nanmax(ys) <= 0:
        return None, None, "nonpositive_curve"
    t0 = float(np.interp(0.0, xs, ys) / 1e6)
    if target_latency < xs[0] or target_latency > xs[-1]:
        return t0, None, f"target_outside_range_{xs[0]:g}_{xs[-1]:g}"
    return t0, float(np.interp(target_latency, xs, ys) / 1e6), "ok"


def lgs_curve_from_stats(output_dir: Path, node_count: int, out_dir: Path) -> Path | None:
    stats_dir = output_dir / "stats"
    if not stats_dir.exists():
        return None
    rows = []
    for path in sorted(stats_dir.glob("lgs_L*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "L" not in payload or "runtime_ns" not in payload:
            continue
        rows.append({
            "L": float(payload["L"]),
            "runtime": float(payload["runtime_ns"]),
            "elapsed_s": payload.get("elapsed_s"),
            "peak_rss_mb": payload.get("peak_rss_mb"),
            "source_json": str(path),
        })
    if not rows:
        return None
    curve = pd.DataFrame(rows).sort_values("L")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grok_N{node_count}_lgs_from_stats.csv"
    curve.to_csv(out_path, index=False)
    return out_path


def hw_reference_ms(analysis_dir: Path) -> dict[str, Any]:
    ci_path = analysis_dir / "collective_instances.csv"
    if not ci_path.exists():
        return {"hw_status": "missing_collective_instances"}
    ci = pd.read_csv(ci_path)
    walls = []
    for rank in ci["goal_rank"].unique():
        rank_rows = ci[ci["goal_rank"] == rank]
        walls.append((rank_rows["end"].max() - rank_rows["start"].min()) / 1e6)
    return {
        "hw_status": "ok",
        "hw_ms_max": float(max(walls)),
        "hw_ms_mean": float(np.mean(walls)),
        "hw_rank_count": int(len(walls)),
        "collective_rows": int(len(ci)),
        "collective_instances": str(ci_path),
    }


def pct_diff(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0:
        return None
    return 100.0 * (value - reference) / reference


def markdown_table(df: pd.DataFrame) -> str:
    headers = [str(col) for col in df.columns]
    rows = []
    for _, row in df.iterrows():
        cells = []
        for value in row.tolist():
            if pd.isna(value):
                cells.append("")
            elif isinstance(value, (float, np.floating)):
                cells.append(f"{value:.3f}")
            else:
                cells.append(str(value))
        rows.append(cells)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def add_curve(row: dict[str, Any], prefix: str, path: Path | None, target_latency: float) -> None:
    if path is None:
        row[f"{prefix}_status"] = "missing"
        row[f"{prefix}_source"] = ""
        row[f"{prefix}_t0_ms"] = None
        row[f"{prefix}_target_ms"] = None
        return
    try:
        t0_ms, target_ms, status = load_curve_ms(path, target_latency)
    except Exception as exc:
        t0_ms, target_ms, status = None, None, f"error:{exc}"
    row[f"{prefix}_status"] = status
    row[f"{prefix}_source"] = str(path)
    row[f"{prefix}_t0_ms"] = t0_ms
    row[f"{prefix}_target_ms"] = target_ms


def add_monolithic_metadata(row: dict[str, Any], path: Path | None) -> None:
    defaults = {
        "monolithic_lp_metadata_source": "",
        "monolithic_lp_wall_s": None,
        "monolithic_lp_rss_mb": None,
        "monolithic_lp_num_vertices": None,
        "monolithic_lp_num_edges": None,
        "monolithic_lp_num_vars": None,
        "monolithic_lp_num_constraints": None,
    }
    row.update(defaults)
    if path is None:
        return
    metadata_path = path.with_suffix(path.suffix + ".json")
    if not metadata_path.exists():
        return
    try:
        with metadata_path.open(encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as exc:
        row["monolithic_lp_metadata_source"] = f"error:{metadata_path}:{exc}"
        return
    row.update({
        "monolithic_lp_metadata_source": str(metadata_path),
        "monolithic_lp_wall_s": metadata.get("wall_s"),
        "monolithic_lp_rss_mb": metadata.get("rss_mb"),
        "monolithic_lp_num_vertices": metadata.get("num_vertices"),
        "monolithic_lp_num_edges": metadata.get("num_edges"),
        "monolithic_lp_num_vars": metadata.get("num_vars"),
        "monolithic_lp_num_constraints": metadata.get("num_constraints"),
    })


def grok_row(node_count: int, args: argparse.Namespace, target_latency: float) -> dict[str, Any]:
    roots = scratch_roots(args)
    analysis_dir = first_existing([
        root / "workspaces" / "grok" / f"N{node_count}" / "analysis"
        for root in roots
    ]) or roots[0] / "workspaces" / "grok" / f"N{node_count}" / "analysis"
    output_dir = first_existing([
        root / "output" / f"grok_n{node_count}"
        for root in roots
    ]) or roots[0] / "output" / f"grok_n{node_count}"
    goal = analysis_dir / "output.goal"
    sidecar_candidates = [
        output_dir / "output.comm-dep",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_commdep_lgs" / "comm_dep.csv",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_commdep" / "comm_dep.csv",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_commdep_goalmatch" / "comm_dep.csv",
    ]
    monolithic_candidates = [
        ROOT / "data" / "revalidation" / f"grok_node_scaling/monolithic_N{node_count}_points/full_runtime.csv",
        ROOT / "data" / "revalidation" / f"grok_node_scaling/monolithic_N{node_count}/sweeps/full_runtime.csv",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_lp/full_runtime.csv",
    ]
    composite_candidates = [
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_composite_row_nranks_regen" / "comp" / "sweeps" / "composed_runtime.csv",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_composite_row_nranks_warm" / "comp" / "sweeps" / "composed_runtime.csv",
        ROOT / "data" / "revalidation" / f"grok_N{node_count}_composite_regen" / "comp" / "sweeps" / "composed_runtime.csv",
    ]
    composite_candidates.extend(
        root / "output" / f"grok_n{node_count}" / "comp" / "sweeps" / "composed_runtime.csv"
        for root in roots
    )
    if args.include_legacy_monolithic:
        monolithic_candidates.append(output_dir / "monolithic" / "sweeps" / "full_runtime.csv")

    row: dict[str, Any] = {
        "node_count": node_count,
        "gpu_count": node_count * args.gpus_per_node,
        "input_class": "scratch_real_grok",
        "goal_source": str(goal) if goal.exists() else "",
        "goal_available": goal.exists() and goal.stat().st_size > 1024,
        "goal_size_mb": goal.stat().st_size / 1e6 if goal.exists() else None,
        "sidecar_source": "",
        "sidecar_available": False,
        "sidecar_size_mb": None,
    }
    sidecar = first_existing(sidecar_candidates)
    if sidecar is not None:
        row["sidecar_source"] = str(sidecar)
        row["sidecar_available"] = True
        row["sidecar_size_mb"] = sidecar.stat().st_size / 1e6
    row.update(hw_reference_ms(analysis_dir))
    add_curve(row, "composite_lp", first_existing(composite_candidates), target_latency)
    lgs_csv = first_existing([
        root / "output" / f"grok_n{node_count}" / "lgs" / "sweeps" / "lgs_runtime.csv"
        for root in roots
    ])
    if lgs_csv is None:
        for root in roots:
            candidate = lgs_curve_from_stats(
                root / "output" / f"grok_n{node_count}",
                node_count,
                args.out_dir / "derived_lgs",
            )
            if candidate is not None:
                lgs_csv = candidate
                break
    add_curve(row, "lgs", lgs_csv, target_latency)
    monolithic_path = None if args.exclude_monolithic else first_existing(monolithic_candidates)
    add_curve(row, "monolithic_lp", monolithic_path, target_latency)
    add_monolithic_metadata(row, monolithic_path)
    return row


def packaged_large_row(node_count: int, args: argparse.Namespace, target_latency: float) -> dict[str, Any]:
    lat = ROOT / "data" / "output" / "grok_final" / f"grok_N{node_count}_latency_sweep.csv"
    summary = ROOT / "data" / "output" / "grok_final" / f"grok_N{node_count}_summary.csv"
    row: dict[str, Any] = {
        "node_count": node_count,
        "gpu_count": None,
        "input_class": "packaged_large_composite_only",
        "goal_source": "",
        "goal_available": False,
        "goal_size_mb": None,
        "sidecar_source": "",
        "sidecar_available": False,
        "sidecar_size_mb": None,
    }
    if summary.exists():
        sr = pd.read_csv(summary).iloc[0]
        row.update({
            "gpu_count": int(sr["n_gpus"]),
            "hw_status": "ok_packaged_summary",
            "hw_ms_max": float(sr["hw_ms"]),
            "hw_ms_mean": float(sr["hw_ms"]),
            "hw_rank_count": None,
            "collective_rows": int(sr["n_collectives"]),
            "collective_instances": str(summary),
        })
    else:
        row["hw_status"] = "missing_packaged_summary"
    add_curve(row, "composite_lp", lat if lat.exists() else None, target_latency)
    add_curve(row, "lgs", None, target_latency)
    add_curve(row, "monolithic_lp", None, target_latency)
    add_monolithic_metadata(row, None)
    return row


def build_summary(args: argparse.Namespace, target_latency: float) -> pd.DataFrame:
    rows = [grok_row(node, args, target_latency) for node in args.nodes]
    if args.include_packaged_large:
        rows.extend(packaged_large_row(node, args, target_latency) for node in [512, 1024])
    df = pd.DataFrame(rows).sort_values("node_count").reset_index(drop=True)
    df.insert(0, "target_latency_ns", target_latency)
    for prefix in ["composite_lp", "lgs", "monolithic_lp"]:
        df[f"{prefix}_vs_hw_pct"] = [
            pct_diff(value, hw)
            for value, hw in zip(df[f"{prefix}_target_ms"], df["hw_ms_max"])
        ]
    return df


def lat_tag(target_latency: float) -> str:
    return f"L{target_latency:g}".replace(".", "p")


def write_report(df: pd.DataFrame, out_dir: Path, target_latency: float, filename: str = "grok_node_scaling_report.md") -> None:
    report = out_dir / filename
    plotted = df[["node_count", "hw_ms_max", "composite_lp_target_ms", "lgs_target_ms", "monolithic_lp_target_ms"]].copy()
    plotted = plotted.rename(columns={
        "hw_ms_max": "HW ms",
        "composite_lp_target_ms": "Composite-LP ms",
        "lgs_target_ms": "LGS ms",
        "monolithic_lp_target_ms": "Monolithic-LP ms",
    })
    availability = df[[
        "node_count",
        "goal_available",
        "sidecar_available",
        "lgs_status",
        "composite_lp_status",
        "monolithic_lp_status",
        "input_class",
    ]].copy()
    with report.open("w", encoding="utf-8") as f:
        f.write("# Grok Node-Scaling Revalidation\n\n")
        f.write(f"Target network latency: `{target_latency:g} ns`.\n\n")
        f.write("## Runtime Summary\n\n")
        f.write(markdown_table(plotted))
        f.write("\n\n## Availability Matrix\n\n")
        f.write(markdown_table(availability))
        f.write("\n\n")
        if (df["input_class"] == "packaged_large_composite_only").any():
            f.write("Rows marked `packaged_large_composite_only` use packaged Composite-LP summaries only; no GOAL/LGS/Monolithic inputs are bundled for those scales.\n")
        else:
            f.write("Rows in this report are assembled from local metadata, hardware logs, regenerated Composite-LP curves, and available LGS outputs; no packaged-large summary rows are included.\n")


def plot(df: pd.DataFrame, out_dir: Path, target_latency: float) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    series = [
        ("HW logs", "hw_ms_max", "#1f2933", "*", "-"),
        ("Composite LP", "composite_lp_target_ms", "#15616d", "o", "-"),
        ("LogGOPSim", "lgs_target_ms", "#b85c00", "s", "--"),
        ("Monolithic LP", "monolithic_lp_target_ms", "#7c3aed", "D", "-."),
    ]
    for label, column, color, marker, linestyle in series:
        valid = df[["node_count", column]].dropna()
        valid = valid[valid[column] > 0]
        if valid.empty:
            continue
        ax.plot(
            valid["node_count"],
            valid[column],
            marker=marker,
            linestyle=linestyle,
            color=color,
            linewidth=1.9,
            markersize=7,
            label=label,
        )
    ticks = df["node_count"].dropna().astype(int).tolist()
    ax.set_xscale("log", base=2)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_xlabel("Grok node count")
    ax.set_ylabel(f"Runtime at L={target_latency / 1000:g} us (ms)")
    ax.grid(True, which="major", axis="both", alpha=0.22)
    ax.legend(frameon=False, ncol=2)
    ax.set_title("Grok scaling: measured HW vs predicted runtime")
    fig.tight_layout()
    tag = lat_tag(target_latency)
    fig.savefig(out_dir / f"grok_node_scaling_nominal_{tag}.png", dpi=240)
    fig.savefig(out_dir / f"grok_node_scaling_nominal_{tag}.pdf")


def plot_multi_latency(long_df: pd.DataFrame, out_dir: Path) -> None:
    latencies = sorted(long_df["target_latency_ns"].dropna().unique())
    if not latencies:
        return
    ncols = min(3, len(latencies))
    nrows = int(np.ceil(len(latencies) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5.2 * ncols, 4.2 * nrows), squeeze=False, sharey=True)
    series = [
        ("HW logs", "hw_ms_max", "#1f2933", "*", "-"),
        ("Composite LP", "composite_lp_target_ms", "#15616d", "o", "-"),
        ("LogGOPSim", "lgs_target_ms", "#b85c00", "s", "--"),
        ("Monolithic LP", "monolithic_lp_target_ms", "#7c3aed", "D", "-."),
    ]
    for ax, target_latency in zip(axes.flat, latencies):
        df = long_df[long_df["target_latency_ns"] == target_latency]
        for label, column, color, marker, linestyle in series:
            valid = df[["node_count", column]].dropna()
            valid = valid[valid[column] > 0]
            if valid.empty:
                continue
            ax.plot(
                valid["node_count"],
                valid[column],
                marker=marker,
                linestyle=linestyle,
                color=color,
                linewidth=1.8,
                markersize=6,
                label=label,
            )
        ticks = df["node_count"].dropna().astype(int).tolist()
        ax.set_xscale("log", base=2)
        ax.set_xticks(ticks)
        ax.set_xticklabels([str(t) for t in ticks], rotation=0)
        ax.set_title(f"L={target_latency / 1000:g} us")
        ax.grid(True, which="major", axis="both", alpha=0.22)
        ax.set_xlabel("Grok node count")
    for ax in axes[:, 0]:
        ax.set_ylabel("Runtime (ms)")
    for ax in axes.flat[len(latencies):]:
        ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.925), ncol=4, frameon=False)
    fig.suptitle("Grok scaling across latency assumptions", y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out_dir / "grok_node_scaling_multi_latency.png", dpi=240)
    fig.savefig(out_dir / "grok_node_scaling_multi_latency.pdf")


def write_summary_outputs(df: pd.DataFrame, out_dir: Path, target_latency: float, *, tagged: bool) -> None:
    if tagged:
        tag = lat_tag(target_latency)
        csv_path = out_dir / f"grok_node_scaling_summary_{tag}.csv"
        json_path = out_dir / f"grok_node_scaling_summary_{tag}.json"
        report_name = f"grok_node_scaling_report_{tag}.md"
    else:
        csv_path = out_dir / "grok_node_scaling_summary.csv"
        json_path = out_dir / "grok_node_scaling_summary.json"
        report_name = "grok_node_scaling_report.md"
    df.to_csv(csv_path, index=False)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(df.where(pd.notnull(df), None).to_dict(orient="records"), f, indent=2)
        f.write("\n")
    write_report(df, out_dir, target_latency, report_name)
    plot(df, out_dir, target_latency)
    print(f"[grok-node-scaling] wrote {csv_path}")
    print(f"[grok-node-scaling] wrote {json_path}")
    print(f"[grok-node-scaling] wrote {out_dir / report_name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scratch-root", type=Path, default=Path("/mnt/scratch/GrokStudy/repo"),
                    help="Root containing Grok workspaces/output from the high-RAM run.")
    ap.add_argument("--extra-scratch-root", action="append", type=Path,
                    default=[Path("/mnt/scratch/GrokStudyCodex/Traces_Compression")],
                    help="Additional root containing Grok workspaces/output. Can be repeated.")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "revalidation" / "grok_node_scaling")
    ap.add_argument("--target-latency", type=float, default=4000.0,
                    help="Latency point in ns for the node-scaling plot.")
    ap.add_argument("--target-latencies", nargs="+", type=float, default=None,
                    help="Latency points in ns for a multi-panel scaling plot. "
                         "If omitted, only --target-latency is used.")
    ap.add_argument("--nodes", nargs="+", type=int, default=[4, 8, 16, 32, 64, 128])
    ap.add_argument("--include-packaged-large", action="store_true", default=True,
                    help="Include packaged N512/N1024 Composite-LP summary rows.")
    ap.add_argument("--no-packaged-large", dest="include_packaged_large", action="store_false")
    ap.add_argument("--include-legacy-monolithic", action="store_true",
                    help="Allow fallback to older scratch monolithic outputs. "
                         "Default excludes them because earlier logs lacked comm_dep.")
    ap.add_argument("--exclude-monolithic", action="store_true",
                    help="Do not load or plot Monolithic-LP outputs, even if prior outputs exist.")
    ap.add_argument("--gpus-per-node", type=int, default=4)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    target_latencies = args.target_latencies if args.target_latencies else [args.target_latency]
    dfs = []
    for target_latency in target_latencies:
        df = build_summary(args, target_latency)
        dfs.append(df)
        write_summary_outputs(df, args.out_dir, target_latency, tagged=True)
        if target_latency == args.target_latency:
            write_summary_outputs(df, args.out_dir, target_latency, tagged=False)

    long_df = pd.concat(dfs, ignore_index=True)
    multi_csv = args.out_dir / "grok_node_scaling_multi_latency_summary.csv"
    multi_json = args.out_dir / "grok_node_scaling_multi_latency_summary.json"
    long_df.to_csv(multi_csv, index=False)
    with multi_json.open("w", encoding="utf-8") as f:
        json.dump(long_df.where(pd.notnull(long_df), None).to_dict(orient="records"), f, indent=2)
        f.write("\n")
    plot_multi_latency(long_df, args.out_dir)
    print(f"[grok-node-scaling] wrote {multi_csv}")
    print(f"[grok-node-scaling] wrote {multi_json}")
    print(f"[grok-node-scaling] wrote {args.out_dir / 'grok_node_scaling_multi_latency.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
