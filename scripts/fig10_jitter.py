#!/usr/bin/env python3
"""
Jitter analysis: Grok 314B, 1024N / 4096 GPUs.

  (a) Runtime vs jitter fraction (stacked bar)
  (b) Slowdown vs jitter fraction

50x latency inflation: 5 μs → 250 μs.
Two-state model: T(f) = (1-f)*T(L_0) + f*T(L_1).
"""
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "output/final_plots/data"
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.labelsize": 8.8,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 8.8,
    "ytick.labelsize": 10,
    "axes.linewidth": 1.3,
    "grid.linewidth": 0.7,
    "grid.alpha": 0.28,
    "figure.dpi": 300,
})

FRACTIONS = [0.0, 0.001, 0.01, 0.05, 0.10, 0.50]
FRAC_LABELS = ["0%", "0.1%", "1%", "5%", "10%", "50%"]
JITTER_PCT = np.array([0.1, 1.0, 5.0, 10.0, 50.0])

# ── Grok 314B N1024 (4096 GPUs) — Composition ──
T_grok_L0 = 10564134520 / 1e6   # ms
T_grok_L1 = 15689543000 / 1e6   # ms

runtimes_ms = np.array([(1 - f) * T_grok_L0 + f * T_grok_L1 for f in FRACTIONS])
base_ms = runtimes_ms[0]
slowdown_pct = (runtimes_ms[1:] / base_ms - 1.0) * 100.0

# Approximate compute fraction from composition T(L=0)
COMPUTE_MS = T_grok_L0 * 0.55
comm_ms = runtimes_ms - COMPUTE_MS

COMPUTE_COLOR = "#B8BEC6"
COMM_COLORS = ["#F7BFA8", "#FB9D7C", "#FF7B5C", "#FF553E", "#F13324", "#D21419"]
LINE_COLOR = "#1565C0"

# ── Figure ──

max_runtime = max(runtimes_ms)
max_sd = max(slowdown_pct)

fig = plt.figure(figsize=(490.906 / 72.0, 208 / 72.0))
gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.30)
ax_l = fig.add_subplot(gs[0, 0])
ax_r = fig.add_subplot(gs[0, 1])
fig.subplots_adjust(top=0.88, bottom=0.18, left=0.10, right=0.97, wspace=0.32)


# ── (a) Runtime bar chart ──

x = np.arange(len(FRAC_LABELS))
ax_l.bar(x, np.full_like(x, COMPUTE_MS, dtype=float),
         color=COMPUTE_COLOR, edgecolor="white", linewidth=0.5)
ax_l.bar(x, comm_ms, bottom=COMPUTE_MS,
         color=COMM_COLORS, edgecolor="white", linewidth=0.5)

for xi, total in zip(x, runtimes_ms):
    label = f"{total/1e3:.1f}" if total >= 1000 else f"{int(round(total))}"
    ax_l.text(xi, total + max_runtime * 0.012, label,
              ha="center", va="bottom", fontsize=8, rotation=0)

ax_l.set_title("")
ax_l.set_ylabel("Runtime [s]", fontsize=8.8)
ax_l.set_xlabel("Fraction of jittered sends", labelpad=8, fontsize=9.6)
ax_l.set_xticks(x)
ax_l.set_xticklabels(FRAC_LABELS)
ax_l.tick_params(axis="x", labelsize=8.8)
ax_l.set_ylim(0, max_runtime * 1.18)
# Show seconds on y-axis
ax_l.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v/1e3:.0f}"))
ax_l.grid(True, axis="y")
ax_l.legend(
    handles=[
        mpatches.Patch(facecolor=COMPUTE_COLOR, label="Compute"),
        mpatches.Patch(facecolor=COMM_COLORS[3], label="Communication"),
    ],
    loc="upper left", framealpha=0.9, fontsize=9.45,
)

# ── (b) Slowdown ──

ax_r.axhspan(0, 5, color="#8BC48A", alpha=0.30, zorder=0)
ax_r.axhspan(5, 20, color="#F6D28B", alpha=0.30, zorder=0)
ax_r.axhspan(20, max_sd * 1.5, color="#F6A0A0", alpha=0.25, zorder=0)

ax_r.plot(JITTER_PCT, slowdown_pct, "-o", color=LINE_COLOR, lw=3.0, ms=10, zorder=3)

# (dx, dy) in points — place labels clear of the line
offsets = [
    (7, 5),     # 0.1% — right, above
    (-1, 8),  # 1%   — left, above
    (-1, 8),    # 5%   — right, above
    (8, 4),     # 10%  — right, above
    (-8, 4),   # 50%  — left, above
]
for j, (xj, yj) in enumerate(zip(JITTER_PCT, slowdown_pct)):
    dx, dy = offsets[j]
    ha = "right" if dx < 0 else "left"
    ax_r.annotate(f"{yj:.1f}%", (xj, yj), textcoords="offset points",
                 xytext=(dx, dy), fontsize=8.5, color="black", ha=ha,
                 annotation_clip=True)

ax_r.set_xscale("log")
ax_r.set_xlim(0.05, 200)
ax_r.set_ylim(0, max_sd * 1.35)
ax_r.set_title("")
ax_r.set_xlabel("Fraction of jittered sends [%]", labelpad=8, fontsize=9.6)
ax_r.set_ylabel("Slowdown [%]", fontsize=8.8)
ax_r.tick_params(axis="x", labelsize=8.8)
ax_r.grid(True, which="major")
ax_r.legend(
    handles=[
        mpatches.Patch(facecolor="#8BC48A", alpha=0.30, label="< 5 %"),
        mpatches.Patch(facecolor="#F6D28B", alpha=0.30, label="5 -- 20 %"),
        mpatches.Patch(facecolor="#F6A0A0", alpha=0.25, label="> 20 %"),
    ],
    loc="upper left", framealpha=0.92, fontsize=8.4,
    title="Slowdown", title_fontsize=8.9,
)

# ── Save ──

for p in [OUT / "fig_jitter_3panel.pdf", OUT / "fig_jitter_3panel.png"]:
    fig.savefig(p, dpi=300)
print(f"Saved {OUT / 'fig_jitter_3panel.pdf'}")
print(f"Saved {OUT / 'fig_jitter_3panel.png'}")
plt.close(fig)
