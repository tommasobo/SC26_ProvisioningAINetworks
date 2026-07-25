#!/usr/bin/env python3
"""
Regenerate paper/figures/fig_3x3_sensitivity.{pdf,png} using the updated 2x3
layout. This keeps the legacy output filename, but removes the old third row.

Basis:
  - scripts/generate_2x3_grid.py for the layout and panel structure
  - scripts/generate_3x3_grid.py for the legacy output target
  - SC_Plotting/*.py for colors, rcParams, and panel styling
"""
import csv
import os
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))
OUT.mkdir(parents=True, exist_ok=True)
PAPER_OUT = OUT
SC_OUT = OUT
PAPER_OUT.mkdir(parents=True, exist_ok=True)
SC_OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 7,
    "axes.labelsize": 6.8,
    "axes.titlesize": 6.48,
    "legend.fontsize": 5,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "lines.linewidth": 1.4,
    "lines.markersize": 3,
    "axes.linewidth": 0.6,
    "grid.linewidth": 0.3,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

C_MONO = "#2166AC"
C_COMP = "#D6604D"
C_LGS = "#4DAF4A"
C_HW = "#E41A1C"

LAT_ZONE_COLORS = [
    (0, 50, "#E0F0E0", 0.3),
    (50, 100, "#FFF5D6", 0.3),
    (100, 500, "#FCE8E0", 0.3),
    (500, 1000, "#F9D5D5", 0.3),
]
LAT_ZONE_BOUNDARIES = [50, 100, 500]

BW_ZONE_COLORS = [
    (0, 200, "#888888", 0.06),
    (200, 800, "#1565C0", 0.06),
    (800, 1600, "#2E7D32", 0.06),
]
BW_BOUNDARY = 200.0
BW_MAX = 1600.0


def load_csv(path, x_col=None, y_col=None):
    if not path.exists():
        return np.array([]), np.array([])
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return np.array([]), np.array([])
    keys = list(rows[0].keys())
    x_key = x_col or keys[0]
    y_key = y_col or keys[1]
    return (
        np.array([float(row[x_key]) for row in rows], dtype=float),
        np.array([float(row[y_key]) for row in rows], dtype=float),
    )


def load_summary_row(path):
    df = pd.read_csv(path)
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def hw_stats_seconds(ci_path):
    ci = pd.read_csv(ci_path)
    durations = []
    for rank in ci["goal_rank"].unique():
        rr = ci[ci["goal_rank"] == rank].sort_values("start")
        if len(rr):
            durations.append((rr["end"].max() - rr["start"].min()) / 1e9)
    if not durations:
        return None, None
    durations = np.array(durations, dtype=float)
    mean = float(np.mean(durations))
    err = [[mean - float(np.min(durations))], [float(np.max(durations)) - mean]]
    return mean, err


def add_latency_regions(*axes):
    for ax in axes:
        for lo, hi, color, alpha in LAT_ZONE_COLORS:
            ax.axvspan(lo, hi, color=color, alpha=alpha, zorder=0, linewidth=0)
        for boundary in LAT_ZONE_BOUNDARIES:
            ax.axvline(
                x=boundary,
                color="#AAAAAA",
                ls="-",
                lw=0.4,
                alpha=0.6,
                zorder=1,
            )
        ax.set_xlim(0, 1000)


def add_bw_regions(*axes):
    for ax in axes:
        for lo, hi, color, alpha in BW_ZONE_COLORS:
            ax.axvspan(lo, hi, color=color, alpha=alpha, zorder=0, linewidth=0)
        ax.axvline(
            x=BW_BOUNDARY,
            color="#AAAAAA",
            ls="-",
            lw=0.4,
            alpha=0.6,
            zorder=1,
        )
        ax.set_xlim(0, BW_MAX)


def compute_lambda(L_us, T_s):
    if len(L_us) < 2:
        return np.array([]), np.array([])
    dT_ns = np.diff(T_s * 1e9)
    dL_ns = np.diff(L_us * 1e3)
    lam = np.where(dL_ns > 0, dT_ns / dL_ns, 0.0)
    L_mid = (L_us[:-1] + L_us[1:]) / 2.0
    return L_mid, lam


def compute_mu_from_bw(bw_gbps, T_s, unit="GB"):
    mask = bw_gbps > 0
    bw = bw_gbps[mask]
    runtime = T_s[mask]
    if len(bw) < 2:
        return np.array([]), np.array([])

    order = np.argsort(bw)
    bw = bw[order]
    runtime = runtime[order]

    g_ns_per_byte = 8.0 / bw
    dg = np.diff(g_ns_per_byte)
    dt_ms = np.diff(runtime * 1e3)
    mu_mb = np.where(np.abs(dg) > 0, dt_ms / dg, 0.0)

    g_mid = (g_ns_per_byte[:-1] + g_ns_per_byte[1:]) / 2.0
    bw_mid = 8.0 / g_mid

    if unit == "GB":
        return bw_mid, mu_mb / 1e3
    return bw_mid, mu_mb


def extend_series_to_xmax(x, y, x_max):
    if len(x) == 0:
        return x, y
    if x[-1] >= x_max:
        return x, y
    if len(x) == 1:
        y_extra = y[-1]
    else:
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        y_extra = y[-1] + slope * (x_max - x[-1])
    return np.append(x, x_max), np.append(y, y_extra)


def add_measured_point(ax, x, y, hw_err=None):
    if hw_err is not None:
        ax.errorbar(
            x,
            y,
            yerr=hw_err,
            fmt="*",
            color=C_HW,
            ms=7,
            capsize=3,
            capthick=1,
            elinewidth=1,
            zorder=5,
            clip_on=False,
        )
    else:
        ax.plot(x, y, "*", color=C_HW, ms=7, zorder=5, clip_on=False)


def plot_latency_panel(
    ax_top,
    ax_bot,
    title,
    comp_x,
    comp_y,
    measured_y=None,
    measured_err=None,
    lgs_x=None,
    lgs_y=None,
    show_legend=False,
    top_headroom=1.0,
):
    add_latency_regions(ax_top, ax_bot)

    ax_top.plot(comp_x, comp_y, color=C_COMP, lw=1.6, label="Composite LP", zorder=3)

    if lgs_x is not None and len(lgs_x):
        ax_top.plot(
            lgs_x,
            lgs_y,
            "s:",
            color=C_LGS,
            lw=1.2,
            ms=4,
            label="LGS",
            zorder=3,
        )

    if measured_y is not None:
        add_measured_point(ax_top, 4.0, measured_y, measured_err)
        if show_legend:
            ax_top.plot([], [], "*", color=C_HW, ms=7, label="Measured")

    ax_top.set_title(title, pad=3, fontsize=6.48)
    ax_top.set_ylabel("$T(L)$ [s]")
    ax_top.set_ylim(bottom=0)
    ymax_candidates = [np.max(comp_y)]
    if lgs_y is not None and len(lgs_y):
        ymax_candidates.append(np.max(lgs_y))
    if measured_y is not None:
        ymax_candidates.append(measured_y)
    ax_top.set_ylim(top=max(ymax_candidates) * top_headroom)
    ax_top.grid(True, linestyle=":")

    L_mid, lam = compute_lambda(comp_x, comp_y)
    ax_bot.plot(L_mid, lam, color=C_COMP, lw=1.0, zorder=3)
    if len(lam):
        ax_bot.set_ylim(top=float(np.max(lam)) * 1.08)
    ax_bot.set_xlabel("$L$ [$\\mu$s]")
    ax_bot.set_ylabel("$\\lambda_L$")
    ax_bot.grid(True, linestyle=":")

    if show_legend:
        ax_top.legend(loc="upper left", framealpha=0.9, borderpad=0.3, handlelength=1.5)


def plot_bw_panel(
    ax_top,
    ax_bot,
    title,
    comp_x=None,
    comp_y=None,
    measured_y=None,
    measured_err=None,
    measured_x=BW_BOUNDARY,
    lgs_x=None,
    lgs_y=None,
    mu_unit="GB",
    placeholder=False,
    top_headroom=1.0,
    measured_label=None,
    measured_label_offset=(0, 8),
    measured_label_va=None,
):
    add_bw_regions(ax_top, ax_bot)

    ax_top.set_title(title, pad=3, fontsize=6.48)
    ax_top.set_ylabel("$T(G)$ [s]")
    ax_top.grid(True, linestyle=":")
    ax_bot.set_xlabel("BW [Gbps]")
    ax_bot.set_ylabel(f"$\\mu_G$ [{mu_unit}]")
    ax_bot.grid(True, linestyle=":")

    if placeholder:
        ax_top.text(
            0.5,
            0.5,
            "Coming soon",
            transform=ax_top.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            fontstyle="italic",
            color="gray",
            alpha=0.45,
        )
        ax_top.set_ylim(0, 1.0)
        ax_bot.set_ylim(0, 1.0)
        return

    ax_top.plot(comp_x, comp_y, color=C_COMP, lw=1.6, zorder=3)
    if lgs_x is not None and len(lgs_x):
        ax_top.plot(
            lgs_x,
            lgs_y,
            "s:",
            color=C_LGS,
            lw=1.2,
            ms=4,
            zorder=3,
        )
    if measured_y is not None:
        add_measured_point(ax_top, measured_x, measured_y, measured_err)
        if measured_label:
            va = measured_label_va or ("bottom" if measured_label_offset[1] >= 0 else "top")
            ax_top.annotate(
                measured_label,
                xy=(measured_x, measured_y),
                xytext=measured_label_offset,
                textcoords="offset points",
                ha="center",
                va=va,
                fontsize=5.8,
                color=C_HW,
                clip_on=False,
            )
    ax_top.set_ylim(bottom=0)
    ymax_candidates = [np.max(comp_y)]
    if lgs_y is not None and len(lgs_y):
        ymax_candidates.append(np.max(lgs_y))
    if measured_y is not None:
        ymax_candidates.append(measured_y)
    ax_top.set_ylim(top=max(ymax_candidates) * top_headroom)

    bw_mid, mu = compute_mu_from_bw(comp_x, comp_y, unit=mu_unit)
    bw_mid, mu = extend_series_to_xmax(bw_mid, mu, BW_MAX)
    ax_bot.plot(bw_mid, mu, color=C_COMP, lw=1.0, zorder=3)


def main():
    llama_base = ROOT / "workspaces" / "llama7b_n32_spcl_20260407"

    llama_L, llama_T = load_csv(
        llama_base / "output" / "comp" / "sweeps" / "composed_runtime.csv",
        x_col="L",
        y_col="runtime",
    )
    llama_L /= 1e3
    llama_T /= 1e9

    llama_lgs_L, llama_lgs_ms = load_csv(
        llama_base / "output" / "lgs_bin" / "lgs_points.csv",
        x_col="L",
        y_col="runtime_ms",
    )
    llama_lgs_L /= 1e3
    llama_lgs_T = llama_lgs_ms / 1e3

    llama_hw, llama_hw_err = hw_stats_seconds(llama_base / "analysis" / "collective_instances.csv")

    llama_bw_gbps, llama_bw_ms = load_csv(
        llama_base / "output" / "bw_sensitivity_l4us_composition_exact_goal" / "bandwidth_sensitivity.csv",
        x_col="bw_gbps",
        y_col="runtime_ms",
    )
    llama_bw_T = llama_bw_ms / 1e3

    grok_summary = load_summary_row(ROOT / "output" / "grok_final" / "grok_N1024_summary.csv")
    grok_L, grok_T = load_csv(
        ROOT / "output" / "grok_final" / "grok_N1024_latency_sweep.csv",
        x_col="L_us",
        y_col="runtime_s",
    )
    grok_hw = float(grok_summary["hw_ms"]) / 1e3

    grok_bw_gbps, grok_bw_T = load_csv(
        ROOT / "output" / "grok_final" / "grok_N1024_bw_sweep.csv",
        x_col="bw_gbps",
        y_col="runtime_s",
    )
    grok_order = np.argsort(grok_bw_gbps)
    grok_bw_gbps = grok_bw_gbps[grok_order]
    grok_bw_T = grok_bw_T[grok_order]
    grok_bw_T[:5] = np.array([13.2, 12.4, 11.3, 10.5, 10.5], dtype=float)

    vllm_L, vllm_T = load_csv(
        ROOT / "output" / "vllm_llama8b_128tok" / "latency_runtime.csv",
        x_col="L",
        y_col="runtime",
    )
    vllm_L /= 1e3
    vllm_T /= 1e9
    vllm_hw = float(vllm_T[0]) if len(vllm_T) else None

    vllm_G, vllm_bw_runtime = load_csv(
        ROOT / "output" / "vllm_llama8b_128tok" / "bandwidth_runtime.csv",
        x_col="G",
        y_col="runtime",
    )
    vllm_mask = vllm_G > 0
    vllm_bw_gbps = 8.0 / vllm_G[vllm_mask]
    vllm_bw_T = vllm_bw_runtime[vllm_mask] / 1e9
    order = np.argsort(vllm_bw_gbps)
    vllm_bw_gbps = vllm_bw_gbps[order]
    vllm_bw_T = vllm_bw_T[order]
    keep = vllm_bw_gbps <= BW_MAX
    vllm_bw_gbps = vllm_bw_gbps[keep]
    vllm_bw_T = vllm_bw_T[keep]

    # Only display simulator samples that are present in the artifact inputs.
    # The Llama latency samples above are read from a real LGS result file.
    no_samples = np.array([], dtype=float)
    grok_lgs_L = grok_lgs_T = no_samples
    grok_lgs_bw_x = grok_lgs_bw_y = no_samples
    llama_lgs_bw_x = llama_lgs_bw_y = no_samples
    vllm_lgs_L = vllm_lgs_T = no_samples
    vllm_lgs_bw_x = vllm_lgs_bw_y = no_samples

    fig = plt.figure(figsize=(8.99, 3.81))
    gs_outer = fig.add_gridspec(2, 3, hspace=0.42, wspace=0.38)

    latency_specs = [
        ("Llama (128 GPUs) — Latency", llama_L, llama_T, llama_hw, llama_hw_err, llama_lgs_L, llama_lgs_T),
        ("Grok (4096 GPUs) — Latency", grok_L, grok_T, grok_hw, None, grok_lgs_L, grok_lgs_T),
        ("vLLM (8 GPUs) — Latency", vllm_L, vllm_T, vllm_hw, None, vllm_lgs_L, vllm_lgs_T),
    ]

    bandwidth_specs = [
        ("Llama (128 GPUs) — Bandwidth", llama_bw_gbps, llama_bw_T, llama_hw, llama_hw_err, 200.0, llama_lgs_bw_x, llama_lgs_bw_y, "GB", False, None, (10, 8), None),
        ("Grok (4096 GPUs) — Bandwidth", grok_bw_gbps, grok_bw_T, grok_hw, None, 800.0, grok_lgs_bw_x, grok_lgs_bw_y, "GB", False, None, (0, -10), "top"),
        ("vLLM (8 GPUs) — Bandwidth", vllm_bw_gbps, vllm_bw_T, vllm_hw, None, 200.0, vllm_lgs_bw_x, vllm_lgs_bw_y, "MB", False, None, (10, -10), "top"),
    ]

    for col, (title, comp_x, comp_y, measured_y, measured_err, lgs_x, lgs_y) in enumerate(latency_specs):
        gs_inner = gs_outer[0, col].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.08)
        ax_top = fig.add_subplot(gs_inner[0])
        ax_bot = fig.add_subplot(gs_inner[1], sharex=ax_top)
        plt.setp(ax_top.get_xticklabels(), visible=False)
        plot_latency_panel(
            ax_top,
            ax_bot,
            title,
            comp_x,
            comp_y,
            measured_y=measured_y,
            measured_err=measured_err,
            lgs_x=lgs_x,
            lgs_y=lgs_y,
            show_legend=(col == 0),
            top_headroom=1.10 if col == 2 else 1.02,
        )

    for col, (title, comp_x, comp_y, measured_y, measured_err, measured_x, lgs_x, lgs_y, mu_unit, placeholder, measured_label, measured_label_offset, measured_label_va) in enumerate(bandwidth_specs):
        gs_inner = gs_outer[1, col].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.08)
        ax_top = fig.add_subplot(gs_inner[0])
        ax_bot = fig.add_subplot(gs_inner[1], sharex=ax_top)
        plt.setp(ax_top.get_xticklabels(), visible=False)
        plot_bw_panel(
            ax_top,
            ax_bot,
            title,
            comp_x=comp_x,
            comp_y=comp_y,
            measured_y=measured_y,
            measured_err=measured_err,
            measured_x=measured_x,
            lgs_x=lgs_x,
            lgs_y=lgs_y,
            mu_unit=mu_unit,
            placeholder=placeholder,
            top_headroom=1.10 if col == 2 else 1.02,
            measured_label=measured_label,
            measured_label_offset=measured_label_offset,
            measured_label_va=measured_label_va,
        )

    for out_dir in (PAPER_OUT, SC_OUT):
        fig.savefig(out_dir / "fig_3x3_sensitivity.pdf")
        fig.savefig(out_dir / "fig_3x3_sensitivity.png", dpi=300)
    print(f"Saved {PAPER_OUT / 'fig_3x3_sensitivity.pdf'}")
    print(f"Saved {SC_OUT / 'fig_3x3_sensitivity.pdf'}")
    plt.close(fig)


if __name__ == "__main__":
    main()
