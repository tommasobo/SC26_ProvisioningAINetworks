#!/usr/bin/env python3
"""Build a compact visual check bundle under images/check."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "images" / "check"
COMPARISONS = ROOT / "results" / "final_scratch_rerun_20260627" / "comparisons"
NEW_PLOTS = ROOT / "new_results" / "final_scratch_rerun_20260627"
FIGURES = ROOT / "figures"


@dataclass(frozen=True)
class PlotSpec:
    label: str
    title: str
    reference_name: str = "Paper/reference"
    regenerated_name: str = "Regenerated"
    x_label: str = "Network latency (us)"
    x_scale: str = "linear"
    x_divisor: float = 1000.0
    y_label: str = "Runtime (ms)"


SPECS = [
    PlotSpec("llama_n32_composite_vs_packaged", "Llama7B N32 Composite-LP latency"),
    PlotSpec(
        "llama_n32_bandwidth_vs_packaged",
        "Llama7B N32 bandwidth sensitivity",
        x_label="Network bandwidth (Gb/s)",
        x_scale="log",
        x_divisor=1.0,
    ),
    PlotSpec("fig03_ch1_vs_packaged", "Fig. 3 AllReduce 128MiB, 16 nodes, 1 channel"),
    PlotSpec("fig03_auto_vs_packaged", "Fig. 3 AllReduce 128MiB, 16 nodes, auto channels"),
    PlotSpec("fig04_mixed_vs_packaged", "Fig. 4 mixed collectives, 16 nodes"),
    PlotSpec("fig5_mono_vs_packaged", "Fig. 5 Llama7B Monolithic-LP from NSYS"),
    PlotSpec("fig5_historical_composite_vs_packaged", "Fig. 5 Llama7B Composite-LP historical mode"),
    PlotSpec(
        "fig5_historical_composite_vs_old_dev",
        "Fig. 5 historical Composite-LP vs old development output",
        reference_name="Old development",
    ),
    PlotSpec(
        "grok_N4_composite_vs_development",
        "Grok N4 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N8_composite_vs_development",
        "Grok N8 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N16_composite_vs_development",
        "Grok N16 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N32_composite_vs_development",
        "Grok N32 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N64_composite_vs_development",
        "Grok N64 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N256_composite_vs_development",
        "Grok N256 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N512_composite_vs_development",
        "Grok N512 Composite-LP",
        reference_name="Development reference",
    ),
    PlotSpec(
        "grok_N128_lgs_vs_previous_regen",
        "Grok N128 LogGOPSim replay",
        reference_name="Previous regeneration",
    ),
    PlotSpec(
        "grok_N256_lgs_vs_development_stats",
        "Grok N256 LogGOPSim replay",
        reference_name="Development stats",
    ),
]


def ensure_dirs() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for subdir in [
        OUT / "standalone" / "regenerated_curves",
        OUT / "standalone" / "paper_reference_curves",
        OUT / "standalone" / "paper_figures",
        OUT / "standalone" / "new_plots",
        OUT / "side_by_side",
    ]:
        subdir.mkdir(parents=True, exist_ok=True)


def load_summary(label: str) -> dict:
    path = COMPARISONS / label / f"{label}_summary.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def detail_path(label: str) -> Path:
    return COMPARISONS / label / f"{label}_detail.csv"


def format_metric(summary: dict) -> str:
    return (
        f"points={summary['n_points']} | "
        f"max rel diff={summary['max_abs_rel_diff_pct']:.4g}% | "
        f"mean rel diff={summary['mean_abs_rel_diff_pct']:.4g}%"
    )


def prep_xy(df: pd.DataFrame, spec: PlotSpec, column: str) -> tuple[pd.Series, pd.Series]:
    x = pd.to_numeric(df["L"], errors="coerce") / spec.x_divisor
    y = pd.to_numeric(df[column], errors="coerce") / 1e6
    mask = x.notna() & y.notna()
    return x[mask], y[mask]


def style_axis(ax: plt.Axes, spec: PlotSpec) -> None:
    ax.set_xlabel(spec.x_label)
    ax.set_ylabel(spec.y_label)
    ax.grid(True, alpha=0.22, linewidth=0.8)
    if spec.x_scale == "log":
        ax.set_xscale("log")


def save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_single(df: pd.DataFrame, spec: PlotSpec, summary: dict, *, reference: bool) -> None:
    column = "expected_runtime" if reference else "actual_runtime"
    label = spec.reference_name if reference else spec.regenerated_name
    out_dir = OUT / "standalone" / ("paper_reference_curves" if reference else "regenerated_curves")
    x, y = prep_xy(df, spec, column)

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(x, y, color="#126a73" if not reference else "#374151", linewidth=2.4)
    ax.scatter(x.iloc[[0, -1]], y.iloc[[0, -1]], color="#126a73" if not reference else "#374151", s=28)
    style_axis(ax, spec)
    ax.set_title(f"{spec.title}\n{label}", loc="left", fontsize=12, fontweight="bold")
    ax.text(
        0.0,
        -0.24,
        format_metric(summary),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#4b5563",
    )
    save(fig, out_dir / spec.label)


def plot_side_by_side(df: pd.DataFrame, spec: PlotSpec, summary: dict) -> None:
    x_ref, y_ref = prep_xy(df, spec, "expected_runtime")
    x_actual, y_actual = prep_xy(df, spec, "actual_runtime")
    ymin = min(float(y_ref.min()), float(y_actual.min()))
    ymax = max(float(y_ref.max()), float(y_actual.max()))
    pad = (ymax - ymin) * 0.08 if ymax > ymin else max(ymax, 1.0) * 0.08

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8), sharey=True)
    for ax, x, y, title, color in [
        (axes[0], x_ref, y_ref, spec.reference_name, "#374151"),
        (axes[1], x_actual, y_actual, spec.regenerated_name, "#126a73"),
    ]:
        ax.plot(x, y, color=color, linewidth=2.5)
        ax.scatter(x.iloc[[0, -1]], y.iloc[[0, -1]], color=color, s=30)
        ax.set_ylim(ymin - pad, ymax + pad)
        style_axis(ax, spec)
        ax.set_title(title, fontsize=11, fontweight="bold")
    fig.suptitle(spec.title, x=0.02, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.02, format_metric(summary), fontsize=9, color="#4b5563")
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    save(fig, OUT / "side_by_side" / spec.label)


def copy_tree_files(src_dir: Path, dst_dir: Path, names: list[str] | None = None) -> list[Path]:
    copied: list[Path] = []
    if not src_dir.exists():
        return copied
    if names is None:
        files = [p for p in src_dir.iterdir() if p.is_file()]
    else:
        files = [src_dir / name for name in names]
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src in files:
        if not src.exists() or not src.is_file():
            continue
        dst = dst_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def copy_assets() -> tuple[list[Path], list[Path]]:
    paper_figures = copy_tree_files(
        FIGURES,
        OUT / "standalone" / "paper_figures",
        [
            "fig_2d_sensitivity_workloads.png",
            "fig_2d_sensitivity_workloads.pdf",
            "fig_3x3_sensitivity.png",
            "fig_3x3_sensitivity.pdf",
            "fig3_sensitivity_1x4.png",
            "fig3_sensitivity_1x4.pdf",
            "fig3_sensitivity_2x2.png",
            "fig3_sensitivity_2x2.pdf",
            "fig_mixed_16n_ch1.png",
            "fig_mixed_16n_ch1.pdf",
            "fig5_llama7b.png",
            "fig5_llama7b.pdf",
            "fig6_grok_memory.png",
            "fig6_grok_memory.pdf",
            "fig_network_perf_combined.png",
            "fig_network_perf_combined.pdf",
            "fig_jitter_3panel.png",
            "fig_jitter_3panel.pdf",
        ],
    )
    new_plots = copy_tree_files(
        NEW_PLOTS,
        OUT / "standalone" / "new_plots",
        [
            "grok_node_scaling_multi_latency.png",
            "grok_node_scaling_multi_latency.pdf",
            "grok_node_scaling_nominal_L0.png",
            "grok_node_scaling_nominal_L0.pdf",
            "grok_node_scaling_nominal_L4000.png",
            "grok_node_scaling_nominal_L4000.pdf",
            "grok_node_scaling_nominal_L250000.png",
            "grok_node_scaling_nominal_L250000.pdf",
            "grok_node_scaling_nominal_L500000.png",
            "grok_node_scaling_nominal_L500000.pdf",
            "grok_node_scaling_nominal_L1e+06.png",
            "grok_node_scaling_nominal_L1e+06.pdf",
        ],
    )
    return paper_figures, new_plots


def write_index(generated: list[str], paper_figures: list[Path], new_plots: list[Path]) -> None:
    lines = [
        "# Visual Check Bundle",
        "",
        "This directory contains compact visual checks from the final scratch rerun.",
        "",
        "## Layout",
        "",
        "- `standalone/regenerated_curves/`: regenerated curve only.",
        "- `standalone/paper_reference_curves/`: packaged paper/reference curve only.",
        "- `side_by_side/`: reference curve beside regenerated curve with matched axes.",
        "- `standalone/paper_figures/`: packaged paper figure redraws from `figures/`.",
        "- `standalone/new_plots/`: requested new Grok node-scaling plots.",
        "",
        "The side-by-side plots are generated from numeric comparison CSVs under `results/final_scratch_rerun_20260627/comparisons/`. For Grok comparison plots, the reference is the local development replay output rather than a paper PDF figure.",
        "",
        "## Generated Comparisons",
        "",
    ]
    lines.extend(f"- `{label}`" for label in generated)
    lines.extend([
        "",
        "## Copied Paper Figure Redraws",
        "",
    ])
    lines.extend(f"- `{p.relative_to(OUT)}`" for p in paper_figures)
    lines.extend([
        "",
        "## Copied New Plots",
        "",
    ])
    lines.extend(f"- `{p.relative_to(OUT)}`" for p in new_plots)
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_dirs()
    generated: list[str] = []
    for spec in SPECS:
        path = detail_path(spec.label)
        if not path.exists():
            print(f"[check-images] skip missing {path}")
            continue
        df = pd.read_csv(path)
        summary = load_summary(spec.label)
        plot_single(df, spec, summary, reference=True)
        plot_single(df, spec, summary, reference=False)
        plot_side_by_side(df, spec, summary)
        generated.append(spec.label)
        print(f"[check-images] generated {spec.label}")
    paper_figures, new_plots = copy_assets()
    write_index(generated, paper_figures, new_plots)
    print(f"[check-images] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
