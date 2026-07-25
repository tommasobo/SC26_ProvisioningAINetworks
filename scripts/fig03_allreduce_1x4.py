#!/usr/bin/env python3
"""
Generate paper figure: 2x2 grid and 1x4 strip of sensitivity plots.

Layout (2x2):
  Top-left:     Latency,   Ch1  (16N, 128MiB)
  Top-right:    Latency,   Auto (16N, 128MiB)
  Bottom-left:  Bandwidth, Ch1  (16N, 128MiB)
  Bottom-right: Bandwidth, Auto (16N, 128MiB)

Each subplot has T(param) on top and sensitivity (lambda or mu) on bottom.
"""
import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "output/final_plots/data"
FULL_RUN = os.environ.get("SC26_FULL_RUN") == "1"
# ── Style ──
plt.rcParams.update({
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "legend.fontsize": 6,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "lines.linewidth": 1.4,
    "lines.markersize": 3,
    "axes.linewidth": 0.6,
    "grid.linewidth": 0.3,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

C_STOCK = "#888888"   # HPC LLAMP
C_COMP  = "#D6604D"   # Composite LP
C_LGS   = "#4DAF4A"   # LGS
C_HW    = "#E41A1C"   # HW


def load_csv(path, x_col=None, y_col="runtime"):
    if not path.exists(): return np.array([]), np.array([])
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows: return np.array([]), np.array([])
    keys = list(rows[0].keys())
    xk = x_col or keys[0]
    return np.array([float(r[xk]) for r in rows]), np.array([float(r[y_col]) for r in rows])


def hw_stats(ci_path):
    ci = pd.read_csv(ci_path)
    ds = []
    for r in ci['goal_rank'].unique():
        rr = ci[ci['goal_rank']==r].sort_values('start')
        if len(rr): ds.append((rr.iloc[0]['end'] - rr.iloc[0]['start'])/1e6)
    return np.mean(ds), np.min(ds), np.max(ds)


def compute_sensitivity(x, y):
    """Compute piecewise dT/dx from data."""
    if len(x) < 2: return x, np.zeros_like(x)
    dx = np.diff(x); dy = np.diff(y)
    s = np.where(dx > 0, dy / dx, 0)
    xm = (x[:-1] + x[1:]) / 2
    return xm, s


def draw_panel(ax_top, ax_bot, x_data, hw_m, hw_err, kind="latency",
               title="", xlabel="", ylabel_top="", ylabel_bot="",
               sensitivity_data=None):
    """Draw one T(param) + sensitivity panel."""

    for label, x, y, color, ls, lw in x_data:
        ax_top.plot(x, y, label=label, color=color, linestyle=ls, linewidth=lw)

    hw_x = 4.0 if kind == "latency" else 200.0  # Slingshot: ~4μs, 200 Gbps
    ax_top.errorbar(hw_x, hw_m, yerr=hw_err, fmt="*", color=C_HW, ms=7,
                    capsize=3, capthick=1, elinewidth=1, zorder=10, clip_on=False)
    # Separate legend entry as plain star (no error bar in legend)
    ax_top.plot([], [], "*", color=C_HW, ms=7, label="Measured")
    if kind == "bandwidth":
        ax_top.axvline(x=0.04, color="gray", ls=":", alpha=0.3, lw=0.5)

    ax_top.set_ylim(bottom=0)
    ax_top.set_ylabel(ylabel_top)
    ax_top.set_title(title, fontsize=8, pad=3)
    ax_top.legend(loc="upper left", framealpha=0.9,
                  borderpad=0.3, handlelength=1.5)
    ax_top.grid(True, linestyle=":")

    # Sensitivity subplot — Composite LP only
    sensitivity_series = x_data
    if sensitivity_data is not None:
        sensitivity_series = [
            ("Composite LP", sensitivity_data[0], sensitivity_data[1],
             C_COMP, "-", 1.0)
        ]
    for label, x, y, color, ls, lw in sensitivity_series:
        if "Composite" not in label: continue
        xm, s = compute_sensitivity(x, y)
        if kind == "latency":
            ax_bot.plot(xm, s * 1e3, color=color, linestyle="-", linewidth=1.0)
        else:
            # x is Gbps, y is ms. Convert back to G-domain for clean μ:
            # Sort by BW, convert to G=8/BW, compute dT/dG in MB
            sort_idx = np.argsort(x)
            bw_sorted = x[sort_idx]
            y_sorted = y[sort_idx]
            g_sorted = 8.0 / bw_sorted  # ns/byte
            # dT(ms)/dG(ns/byte) = MB directly
            dg = np.diff(g_sorted)
            dt = np.diff(y_sorted)
            mu = np.where(np.abs(dg) > 0, dt / dg, 0)
            g_mid = (g_sorted[:-1] + g_sorted[1:]) / 2
            bw_mid = 8.0 / g_mid
            ax_bot.plot(bw_mid, mu, color=color, linestyle="-", linewidth=1.0)

    if kind == "bandwidth":
        ax_bot.axvline(x=200, color="gray", ls=":", alpha=0.3, lw=0.5)
        # BW region bands in Gbps (very subtle, full extent)
        bw_min = 8.0 / 0.12  # ~67 Gbps
        bw_max = 1600  # 1.6 Tbps
        for ax in [ax_top, ax_bot]:
            ax.set_xlim(bw_min, bw_max)
            ax.axvspan(200, 800, alpha=0.06, color="#1565C0", zorder=0)
            ax.axvspan(bw_min - 10, 200, alpha=0.06, color="#888888", zorder=0)
            ax.axvspan(800, bw_max + 100, alpha=0.06, color="#2E7D32", zorder=0)

    # Add latency region bands to ALL plots (very subtle)
    if kind == "latency":
        regions = [
            (0,    50,  "HPC",       "#E0F0E0", "#2E7D32"),
            (50,  100,  "Opt. Cloud","#FFF5D6", "#F57F17"),
            (100, 500,  "Cloud",     "#FCE8E0", "#E65100"),
            (500, 1100, "Inter-DC",  "#F9D5D5", "#B71C1C"),
        ]
        for ax in [ax_top, ax_bot]:
            for x0, x1, lbl, fill, clr in regions:
                ax.axvspan(x0, x1, alpha=0.3, color=fill, zorder=0)
                if x1 < 1100:
                    ax.axvline(x=min(x1, 1000), color="#AAAAAA", ls="-", alpha=0.6, lw=0.4, zorder=1)
            ax.set_xlim(0, 1000)

    ax_bot.set_xlabel(xlabel)
    ax_bot.set_ylabel(ylabel_bot)
    ax_bot.grid(True, linestyle=":")


# ── Load all data ──
EXPS = {
    "ch1":  "ar_128m_16n_ch1",
    "auto": "ar_128m_16n_auto",
}

panels = {}  # (kind, channels) → data dict

for ch_label, exp in EXPS.items():
    d = DATA / exp
    hw_m, hw_lo, hw_hi = hw_stats(d / "collective_instances.csv")
    hw_err = [[hw_m - hw_lo], [hw_hi - hw_m]]

    # Latency
    stock_L, stock_T = load_csv(d / "latency_stock_runtime.csv")
    full_L, full_T   = load_csv(d / "latency_full_runtime.csv")
    comp_L, comp_T   = load_csv(d / "latency_composite_runtime.csv")
    if not len(comp_L):
        comp_L, comp_T = full_L, full_T
    lgs_L, lgs_T     = load_csv(d / "latency_lgs_runtime.csv")

    lat_data = []
    if len(stock_L): lat_data.append(("LLAMP", stock_L/1e3, stock_T/1e6, C_STOCK, "--", 1.2))
    if len(full_L):
        lat_data.append(("Monolithic LP", full_L/1e3, full_T/1e6, "#2166AC", "-", 1.6))
    if len(comp_L):  lat_data.append(("Composite LP", comp_L/1e3, comp_T/1e6, "#D6604D", "-", 1.6))
    if len(lgs_L):   lat_data.append(("LGS", lgs_L/1e3, lgs_T/1e6, C_LGS, "-.", 1.2))

    panels[("latency", ch_label)] = dict(data=lat_data, hw_m=hw_m, hw_err=hw_err)

    # Bandwidth — convert G (ns/byte) to Gbps = 8/G
    stock_G, stock_BT = load_csv(d / "bw_stock_runtime.csv")
    mono_G, mono_BT   = load_csv(d / "bw_monolithic_runtime.csv")
    comp_G, comp_BT   = load_csv(d / "bw_composite_runtime.csv")
    lgs_G, lgs_BT     = load_csv(d / "bw_lgs_runtime.csv")

    def g_to_gbps(G, T):
        mask = G > 0
        return 8.0 / G[mask], T[mask]

    bw_data = []
    if len(stock_G):
        bw_x, bw_y = g_to_gbps(stock_G, stock_BT/1e6)
        bw_data.append(("LLAMP", bw_x, bw_y, C_STOCK, "--", 1.2))
    if len(mono_G):
        bw_x, bw_y = g_to_gbps(mono_G, mono_BT/1e6)
        bw_data.append(("Monolithic LP", bw_x, bw_y, "#2166AC", "-", 1.6))
    elif len(comp_G) and not FULL_RUN:
        bw_x, bw_y = g_to_gbps(comp_G, comp_BT/1e6)
        bw_data.append(("Monolithic LP", bw_x, bw_y, "#2166AC", "-", 1.6))
    if len(comp_G):
        bw_x, bw_y = g_to_gbps(comp_G, comp_BT/1e6)
        bw_data.append(("Composite LP", bw_x, bw_y, "#D6604D", "-", 1.6))
    if len(lgs_G):
        bw_x, bw_y = g_to_gbps(lgs_G, lgs_BT/1e6)
        bw_data.append(("LGS", bw_x, bw_y, C_LGS, "-.", 1.2))

    if len(mono_G):
        sensitivity_bw = g_to_gbps(mono_G, mono_BT / 1e6)
    else:
        sensitivity_bw = g_to_gbps(comp_G, comp_BT / 1e6)
    panels[("bandwidth", ch_label)] = dict(
        data=bw_data,
        hw_m=hw_m,
        hw_err=hw_err,
        sensitivity=sensitivity_bw,
    )


# ═══════════════════════════════════════════════════════════════
#  2x2 grid (half-column width)
# ═══════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(4.3, 4.8))

# 4 main panels, each split into T + sensitivity
gs_outer = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.35)

layout = [
    (0, 0, "latency",   "ch1",  "1 Channel"),
    (0, 1, "latency",   "auto", "8 Channels (Auto)"),
    (1, 0, "bandwidth", "ch1",  "1 Channel"),
    (1, 1, "bandwidth", "auto", "8 Channels (Auto)"),
]

for row, col, kind, ch, subtitle in layout:
    gs_inner = gs_outer[row, col].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.08)
    ax_top = fig.add_subplot(gs_inner[0])
    ax_bot = fig.add_subplot(gs_inner[1], sharex=ax_top)
    plt.setp(ax_top.get_xticklabels(), visible=False)

    p = panels[(kind, ch)]

    if kind == "latency":
        title = f"Latency — {subtitle}"
        xlabel = "$L$ [$\\mu$s]"
        ylabel_top = "$T(L)$ [ms]"
        ylabel_bot = "$\\lambda_L$"
    else:
        title = f"Bandwidth — {subtitle}"
        xlabel = "$G$ [ns/byte]"
        ylabel_top = "$T(G)$ [ms]"
        ylabel_bot = "$\\mu_G$ [MB]"

    draw_panel(ax_top, ax_bot, p["data"], p["hw_m"], p["hw_err"],
               kind=kind, title=title, xlabel=xlabel,
               ylabel_top=ylabel_top, ylabel_bot=ylabel_bot,
               sensitivity_data=p.get("sensitivity"))

    # Only show legend on top-left
    if not (row == 0 and col == 0):
        ax_top.get_legend().remove()

fig.suptitle("AllReduce 128 MiB, 16 Nodes (64 GPUs)", fontsize=9, fontweight="bold", y=0.98)

fig.savefig(OUT / "fig3_sensitivity_2x2.pdf")
fig.savefig(OUT / "fig3_sensitivity_2x2.png", dpi=300)
print(f"Saved {OUT / 'fig3_sensitivity_2x2.pdf'}")
plt.close()


# ═══════════════════════════════════════════════════════════════
#  1x4 strip (full page width)
# ═══════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(10.73, 2.44))

gs_outer = fig.add_gridspec(1, 4, wspace=0.32)

strip_layout = [
    (0, "latency",   "ch1",  "Latency, 1 ch"),
    (1, "latency",   "auto", "Latency, 8 ch"),
    (2, "bandwidth", "ch1",  "Bandwidth, 1 ch"),
    (3, "bandwidth", "auto", "Bandwidth, 8 ch"),
]

for col, kind, ch, subtitle in strip_layout:
    gs_inner = gs_outer[col].subgridspec(2, 1, height_ratios=[2.5, 1], hspace=0.08)
    ax_top = fig.add_subplot(gs_inner[0])
    ax_bot = fig.add_subplot(gs_inner[1], sharex=ax_top)
    plt.setp(ax_top.get_xticklabels(), visible=False)

    p = panels[(kind, ch)]

    # Y-axis labels only on leftmost panel of each type
    if kind == "latency":
        xlabel = "$L$ [$\\mu$s]"
        ylabel_top = "$T(L)$ [ms]" if col == 0 else ""
        ylabel_bot = "$\\lambda_L$" if col == 0 else ""
    else:
        xlabel = "BW [Gbps]"
        ylabel_top = "$T$ [ms]" if col == 2 else ""
        ylabel_bot = "$\\mu_G$ [MB]" if col == 2 else ""

    draw_panel(ax_top, ax_bot, p["data"], p["hw_m"], p["hw_err"],
               kind=kind, title=subtitle, xlabel=xlabel,
               ylabel_top=ylabel_top, ylabel_bot=ylabel_bot,
               sensitivity_data=p.get("sensitivity"))

    # Only show legend on first panel
    if col != 0:
        leg = ax_top.get_legend()
        if leg: leg.remove()

    # Region labels only on second latency subplot (col==1)
    if kind == "latency" and col == 1:
        ymax = ax_top.get_ylim()[1]
        # HPC: arrow from outside, well to the left
        ax_top.annotate("HPC", xy=(25, ymax*0.75),
                        xytext=(-70, ymax*1.08), textcoords="data",
                        ha="center", va="bottom", fontsize=5, color="#2E7D32",
                        fontweight="bold", zorder=5, clip_on=False,
                        arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=0.6))
        # Opt. Cloud: offset right, clear of HPC
        ax_top.annotate("Opt. Cloud", xy=(75, ymax*0.75),
                        xytext=(175, ymax*1.08), textcoords="data",
                        ha="center", va="bottom", fontsize=5, color="#F57F17",
                        fontweight="bold", zorder=5, clip_on=False,
                        arrowprops=dict(arrowstyle="->", color="#F57F17", lw=0.6))
        # Inside plot
        ax_top.text(300, ymax*0.95, "TCP\nIntra-DC", ha="center", va="top",
                    fontsize=5, color="#E65100", fontweight="bold", zorder=5)
        ax_top.text(750, ymax*0.95, "Metro\nInter-DC", ha="center", va="top",
                    fontsize=5, color="#B71C1C", fontweight="bold", zorder=5)

    # Region labels for bandwidth (col==3, second BW plot)
    if kind == "bandwidth" and col == 3:
        ymax_bw = ax_top.get_ylim()[1]
        ax_top.text(500, ymax_bw*0.95, "Modern\nSwitches",
                    ha="center", va="top", fontsize=4.5, color="#1565C0",
                    fontweight="bold", zorder=5)
        # Legacy: outside plot with arrow pointing into the low-BW region
        ax_top.annotate("Legacy\nSwitches", xy=(150, ymax_bw*0.85),
                        xytext=(30, ymax_bw*1.08), textcoords="data",
                        ha="center", va="bottom", fontsize=4.5, color="#888888",
                        fontweight="bold", zorder=5, clip_on=False,
                        arrowprops=dict(arrowstyle="->", color="#888888", lw=0.6))
        ax_top.text(1200, ymax_bw*0.95, "Future\nSwitches",
                    ha="center", va="top", fontsize=4.5, color="#2E7D32",
                    fontweight="bold", zorder=5)

    # Overlap annotation on first latency subplot (col==0)
    if kind == "latency" and col == 0 and not FULL_RUN:
        from matplotlib.offsetbox import HPacker, TextArea, AnchoredOffsetbox, VPacker
        FS = 6
        line1 = [TextArea("Monolithic LP", textprops=dict(fontsize=FS, fontstyle="italic", color="#2166AC")),
                 TextArea(" and", textprops=dict(fontsize=FS, fontstyle="italic", color="black"))]
        line2 = [TextArea("Composite LP", textprops=dict(fontsize=FS, fontstyle="italic", color="#D6604D")),
                 TextArea(" overlap", textprops=dict(fontsize=FS, fontstyle="italic", color="black"))]
        box = VPacker(children=[HPacker(children=line1, pad=0, sep=1, align="baseline"),
                                 HPacker(children=line2, pad=0, sep=1, align="baseline")],
                      pad=0, sep=1, align="left")
        ax_top.add_artist(AnchoredOffsetbox(loc="lower right", child=box, pad=0.3, frameon=False,
                                             bbox_to_anchor=(1.025, 0.21), bbox_transform=ax_top.transAxes))


fig.savefig(OUT / "fig3_sensitivity_1x4.pdf")
fig.savefig(OUT / "fig3_sensitivity_1x4.png", dpi=300)
print(f"Saved {OUT / 'fig3_sensitivity_1x4.pdf'}")
plt.close()

print("Done.")
