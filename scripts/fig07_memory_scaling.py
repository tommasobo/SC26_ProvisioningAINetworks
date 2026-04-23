#!/usr/bin/env python3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = ART_ROOT / "data"
OUT = ART_ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5, "legend.fontsize": 6,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "lines.linewidth": 1.4, "lines.markersize": 3,
    "axes.linewidth": 0.6, "grid.linewidth": 0.3, "grid.alpha": 0.3, "figure.dpi": 300,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})

# --- Data ---
# Monolithic LP peak memory for Grok 314B at different node counts
CONFIGS = ["N4", "N8", "N16", "N32", "N64", "N128", "N256", "N512", "N1024"]
GPUS    = [16,    32,   64,   128,   256,   512,    1024,  2048,   4096]
MEM_GB  = [8,     10,   22,    59,   146,   389,    1740,  7782,  34816]
# N4-N128: measured from actual Gurobi runs; N256-N1024: extrapolated from scaling trend
MEASURED_COUNT = 6  # first 6 entries are measured

COMP_MEM_TB = 0.2  # Composition solver peak memory at N1024

C_MEASURED = "#2F5496"
C_EXTRAP   = "#BDD7EE"
C_TREND    = "#C0504D"

def fmt_mem(gb):
    if gb >= 1024:
        return f"{gb / 1024:.1f} TB"
    return f"{gb:.0f} GB"

fig, ax = plt.subplots(figsize=(4.5, 1.66))

x = np.arange(len(CONFIGS))
mem = np.array(MEM_GB, dtype=float)

# Bars: measured vs extrapolated
bars_m = ax.bar(x[:MEASURED_COUNT], mem[:MEASURED_COUNT], color=C_MEASURED, edgecolor="none", width=0.6, zorder=3)
bars_e = ax.bar(x[MEASURED_COUNT:], mem[MEASURED_COUNT:], color=C_EXTRAP, edgecolor="none", width=0.6, zorder=3)

# Red dashed trendline
ax.plot(x, mem, "o--", color=C_TREND, ms=4, lw=1.3, mec=C_TREND, mfc="#E8A0A0", zorder=4)

# Bar labels
for i, (xi, mi) in enumerate(zip(x, mem)):
    label = fmt_mem(mi)
    ax.text(xi, mi * 1.15, label, ha="center", va="bottom", fontsize=5.5, zorder=5)

# X-axis
xlabels = [f"{c}\n({g})" for c, g in zip(CONFIGS, GPUS)]
ax.set_xticks(x)
ax.set_xticklabels(xlabels)

# Y-axis log scale
ax.set_yscale("log")
ax.set_ylabel("Peak Memory [GB]")
ax.set_ylim(5, 1e5)

# Legend — use proxy patches so colors match the bars exactly
import matplotlib.patches as mpatches
p_meas = mpatches.Patch(facecolor=C_MEASURED, edgecolor="none", label="Measured")
p_ext  = mpatches.Patch(facecolor=C_EXTRAP, edgecolor="none", label="Extrapolated")
ax.legend(handles=[p_meas, p_ext], loc="upper left", framealpha=0.9, borderpad=0.3, handlelength=1.2)

# Annotation: N1024 comparison
mono_tb = MEM_GB[-1] / 1024
ratio = int(round(mono_tb / COMP_MEM_TB))
ann_text = (f"At N1024: Monolithic LP needs ~{mono_tb:.0f} TB\n"
            f"vs Composition LP ~{COMP_MEM_TB} TB\n"
            f"({ratio} times less memory)")
ax.annotate(
    ann_text,
    xy=(x[-1], mem[-1] * 0.5),
    xytext=(0.52, 0.08),
    textcoords="axes fraction",
    fontsize=5.5, fontstyle="italic", color="#333",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#F5F5F5", edgecolor="#BBBBBB", alpha=0.95),
    arrowprops=dict(arrowstyle="->", color="#777777", lw=0.8, shrinkA=0, shrinkB=3),
    zorder=10,
)

ax.grid(True, linestyle=":", axis="y")

fig.savefig(OUT / "fig6_grok_memory.pdf")
fig.savefig(OUT / "fig6_grok_memory.png", dpi=300)
print(f"Saved {OUT / 'fig6_grok_memory.pdf'}")
plt.close()
