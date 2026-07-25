#!/usr/bin/env python3
"""Reproduce paper Figures 8 and 9 from the compact sweep tables."""

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ART_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT_DIR = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))

LLAMA_LAT = (
    DATA_ROOT
    / "workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps"
    / "composed_runtime.csv"
)
LLAMA_BW = (
    DATA_ROOT
    / "workspaces/llama7b_n32_spcl_20260407/output"
    / "bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv"
)
GROK_LAT = DATA_ROOT / "output/grok_final/grok_N1024_latency_sweep.csv"
GROK_BW = DATA_ROOT / "output/grok_final/grok_N1024_bw_sweep.csv"

TIER_BW_GBPS = np.array([100, 200, 400, 800, 1600], dtype=float)
TIER_COST_M = np.array([4, 12, 24, 36, 66], dtype=float)

RED = "#C0392B"
DARK = "#2C3E50"
GREEN = "#2E7D32"
SHADE_ALPHA = 0.06
SCALE_TICKS = np.array([0.1, 0.2, 0.5, 1, 2, 5, 10], dtype=float)

plt.rcParams.update(
    {
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 8,
        "legend.fontsize": 6,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "lines.linewidth": 1.45,
        "axes.linewidth": 0.55,
        "grid.linewidth": 0.3,
        "grid.alpha": 0.3,
        "figure.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.025,
    }
)


def _column(frame: pd.DataFrame, *names: str) -> np.ndarray:
    for name in names:
        if name in frame:
            return frame[name].to_numpy(dtype=float)
    raise ValueError(f"None of {names!r} found in {list(frame.columns)!r}")


def load_sweeps(
    latency_path: Path,
    bandwidth_path: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return latency in microseconds, bandwidth in Gbps, and runtimes."""
    latency = pd.read_csv(latency_path)
    bandwidth = pd.read_csv(bandwidth_path)

    if "L_us" in latency:
        latency_us = latency["L_us"].to_numpy(dtype=float)
    else:
        latency_us = _column(latency, "L", "L_ns") / 1_000.0

    latency_runtime = _column(
        latency, "runtime_ms", "runtime", "runtime_ns", "runtime_s"
    )
    bandwidth_gbps = _column(bandwidth, "bw_gbps")
    bandwidth_runtime = _column(
        bandwidth, "runtime_ms", "runtime", "runtime_ns", "runtime_s"
    )
    return latency_us, latency_runtime, bandwidth_gbps, bandwidth_runtime


def _interp(x: np.ndarray, y: np.ndarray, points: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    return np.interp(points, x[order], y[order])


def _format_bandwidth(value_gbps: float) -> str:
    if value_gbps >= 1_000:
        return f"{value_gbps / 1_000:.1f}Tbps"
    return f"{value_gbps:.0f}Gbps"


def _format_latency(value_us: float) -> str:
    if value_us < 1:
        return f"{value_us:.1f}μs"
    if value_us < 10:
        return f"{value_us:.0f}μs"
    return f"{value_us:.0f}μs"


def plot_parameter_sensitivity(
    ax: plt.Axes,
    sweeps: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    *,
    baseline_latency_us: float,
    baseline_bandwidth_gbps: float,
    title: str,
    baseline_name: str,
    ylim: tuple[float, float],
    legend: bool,
) -> None:
    latency_us, latency_runtime, bandwidth_gbps, bandwidth_runtime = sweeps
    scale = np.geomspace(0.1, 10.0, 201)

    latency_at_scale = _interp(
        latency_us,
        latency_runtime,
        baseline_latency_us / scale,
    )
    bandwidth_at_scale = _interp(
        bandwidth_gbps,
        bandwidth_runtime,
        baseline_bandwidth_gbps * scale,
    )
    latency_baseline = _interp(
        latency_us, latency_runtime, np.array([baseline_latency_us])
    )[0]
    bandwidth_baseline = _interp(
        bandwidth_gbps,
        bandwidth_runtime,
        np.array([baseline_bandwidth_gbps]),
    )[0]

    ax.axvspan(0.1, 1.0, alpha=SHADE_ALPHA, color="#B71C1C", zorder=0)
    ax.axvspan(1.0, 10.0, alpha=SHADE_ALPHA, color=GREEN, zorder=0)
    ax.plot(
        scale,
        bandwidth_baseline / bandwidth_at_scale,
        color=RED,
        label="Changing Bandwidth",
    )
    ax.plot(
        scale,
        latency_baseline / latency_at_scale,
        color=DARK,
        label="Changing Latency",
    )
    ax.axvline(1.0, color="gray", ls="--", alpha=0.5, lw=0.65)
    ax.axhline(1.0, color="gray", ls="--", alpha=0.5, lw=0.65)

    ax.set_xscale("log")
    ax.set_xlim(0.1, 10)
    ax.set_ylim(*ylim)
    ax.set_xticks(SCALE_TICKS)
    ax.set_xticklabels([f"{value:g}x" for value in SCALE_TICKS])
    ax.minorticks_off()
    ax.grid(True, linestyle=":", which="major")
    ax.text(
        0.98,
        0.92,
        title,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=6.2,
        fontweight="bold",
    )
    ax.set_xlabel(f"Scaling factor (1x = {baseline_name})", labelpad=11)

    bandwidth_labels = [
        _format_bandwidth(baseline_bandwidth_gbps * value)
        for value in SCALE_TICKS
    ]
    latency_labels = [
        _format_latency(baseline_latency_us / value) for value in SCALE_TICKS
    ]
    for value, bandwidth_label, latency_label in zip(
        SCALE_TICKS, bandwidth_labels, latency_labels
    ):
        ax.annotate(
            bandwidth_label,
            xy=(value, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -13),
            textcoords="offset points",
            ha="center",
            fontsize=5.2,
            color=RED,
        )
        ax.annotate(
            latency_label,
            xy=(value, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -19),
            textcoords="offset points",
            ha="center",
            fontsize=5.2,
            color=DARK,
        )

    ax.annotate(
        "← Worse L or BW",
        xy=(0.05, 0.28),
        xycoords="axes fraction",
        fontsize=6,
        color="#B71C1C",
        fontstyle="italic",
        alpha=0.7,
        fontweight="bold",
    )
    ax.annotate(
        "Better L or BW →",
        xy=(0.67, 0.28),
        xycoords="axes fraction",
        fontsize=6,
        color=GREEN,
        fontstyle="italic",
        alpha=0.7,
        fontweight="bold",
    )
    if legend:
        ax.legend(loc="upper left", frameon=False, ncol=1)


def plot_cost_performance(ax: plt.Axes, llama_sweeps) -> None:
    _, _, bandwidth_gbps, bandwidth_runtime = llama_sweeps
    baseline_bandwidth_gbps = 200.0
    baseline_runtime = _interp(
        bandwidth_gbps,
        bandwidth_runtime,
        np.array([baseline_bandwidth_gbps]),
    )[0]
    runtime_at_tier = _interp(
        bandwidth_gbps, bandwidth_runtime, TIER_BW_GBPS
    )
    bandwidth_dense = np.linspace(50, 1_600, 500)
    runtime_dense = _interp(
        bandwidth_gbps, bandwidth_runtime, bandwidth_dense
    )
    cost_dense = np.interp(
        bandwidth_dense, TIER_BW_GBPS, TIER_COST_M
    )
    performance_at_tier = baseline_runtime / runtime_at_tier
    performance_dense = baseline_runtime / runtime_dense

    baseline_index = int(np.where(TIER_BW_GBPS == baseline_bandwidth_gbps)[0][0])
    marker_cost = np.delete(TIER_COST_M, baseline_index)
    marker_perf = np.delete(performance_at_tier, baseline_index)
    marker_bw = np.delete(TIER_BW_GBPS, baseline_index)

    ax.plot(cost_dense, performance_dense, color=RED, lw=1.45, zorder=3)
    ax.plot(
        marker_cost,
        marker_perf,
        "D",
        color=RED,
        ms=5,
        mec="white",
        mew=0.5,
        zorder=5,
    )
    offsets = {
        100: (-12, 4, "left"),
        400: (5, 0, "left"),
        800: (0, -12, "center"),
        1600: (-3, -9, "right"),
    }
    for bandwidth, cost, performance in zip(
        marker_bw, marker_cost, marker_perf
    ):
        offset_x, offset_y, horizontal = offsets[int(bandwidth)]
        ax.annotate(
            f"{bandwidth:.0f} Gbps",
            (cost, performance),
            textcoords="offset points",
            xytext=(offset_x, offset_y),
            fontsize=5.2,
            color="#333333",
            fontweight="bold",
            ha=horizontal,
        )

    baseline_cost = np.interp(
        baseline_bandwidth_gbps, TIER_BW_GBPS, TIER_COST_M
    )
    ax.plot(baseline_cost, 1.0, "*", color="black", ms=8, zorder=6)
    ax.annotate(
        "Alps Baseline (200 Gbps)",
        xy=(baseline_cost, 1.0),
        xytext=(8, -1),
        textcoords="offset points",
        fontsize=5.2,
        color="black",
        fontweight="bold",
        ha="left",
        va="center",
    )

    ax.axvspan(-1, TIER_COST_M[3], alpha=SHADE_ALPHA, color=GREEN, zorder=0)
    ax.axvspan(
        TIER_COST_M[3], 100, alpha=SHADE_ALPHA, color="#B71C1C", zorder=0
    )
    ax.text(
        3,
        2.4,
        "High value upgrades",
        fontsize=6,
        fontstyle="italic",
        color=GREEN,
        alpha=0.7,
        fontweight="bold",
    )
    ax.text(
        43,
        2.4,
        "Diminishing returns",
        fontsize=6,
        fontstyle="italic",
        color="#B71C1C",
        alpha=0.7,
        fontweight="bold",
    )
    ax.set_xlabel(
        "Est. network-only cost [$M] (4K GPU fat-tree, fixed GPU config)",
        fontsize=6,
    )
    ax.set_ylabel("Relative performance", fontsize=6)
    ax.set_ylim(
        min(np.min(performance_dense), np.min(performance_at_tier)) * 0.95,
        max(np.max(performance_dense), np.max(performance_at_tier)) * 1.05,
    )
    ax.set_xlim(0, 70)
    ax.grid(True, linestyle=":")
    ax.axhline(1.0, color="gray", ls="--", alpha=0.5, lw=0.65)


def save_figure_8(llama_sweeps, grok_sweeps) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 2.65))
    plot_parameter_sensitivity(
        axes[0],
        llama_sweeps,
        baseline_latency_us=4.0,
        baseline_bandwidth_gbps=200.0,
        title="Llama (128 GPUs)",
        baseline_name="Alps settings",
        ylim=(0, 4.0),
        legend=True,
    )
    plot_parameter_sensitivity(
        axes[1],
        grok_sweeps,
        baseline_latency_us=4.0,
        baseline_bandwidth_gbps=800.0,
        title="Grok (4096 GPUs)",
        baseline_name="Azure ND GB200 v6",
        ylim=(0, 1.25),
        legend=False,
    )
    fig.supylabel("Relative performance", x=0.02, fontsize=7)
    fig.subplots_adjust(
        left=0.17, right=0.99, top=0.96, bottom=0.12, hspace=0.78
    )
    fig.savefig(OUT_DIR / "fig8_network_parameters.pdf")
    fig.savefig(OUT_DIR / "fig8_network_parameters.png", dpi=300)
    plt.close(fig)


def save_figure_9(llama_sweeps) -> None:
    fig, ax = plt.subplots(figsize=(3.8, 1.2))
    plot_cost_performance(ax, llama_sweeps)
    fig.subplots_adjust(left=0.19, right=0.99, top=0.98, bottom=0.34)
    with plt.rc_context({"savefig.bbox": None}):
        fig.savefig(OUT_DIR / "fig9_network_cost.pdf")
        fig.savefig(OUT_DIR / "fig9_network_cost.png", dpi=300)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    llama_sweeps = load_sweeps(LLAMA_LAT, LLAMA_BW)
    grok_sweeps = load_sweeps(GROK_LAT, GROK_BW)
    save_figure_8(llama_sweeps, grok_sweeps)
    save_figure_9(llama_sweeps)
    print("Saved fig8_network_parameters.pdf and fig9_network_cost.pdf")


if __name__ == "__main__":
    main()
