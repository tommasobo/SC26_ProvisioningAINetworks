#!/usr/bin/env python3
import csv, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = ART_ROOT / "data"
OUT = ART_ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.size":7,"axes.labelsize":5.8,"axes.titlesize":6.1,"legend.fontsize":5,
    "xtick.labelsize":5.1,"ytick.labelsize":5.1,"lines.linewidth":1.4,"lines.markersize":3,
    "axes.linewidth":0.6,"grid.linewidth":0.3,"grid.alpha":0.3,"figure.dpi":300,
    "savefig.bbox":"tight","savefig.pad_inches":0.02})

C_MONO="#2166AC"; C_COMP="#D6604D"; C_LGS="#4DAF4A"; C_HW="#E41A1C"

ZONE_COLORS = [
    (0, 50,    "#E0F0E0", 0.3),
    (50, 100,  "#FFF5D6", 0.3),
    (100, 500, "#FCE8E0", 0.3),
    (500, 1000,"#F9D5D5", 0.3),
]
ZONE_BOUNDARIES = [50, 100, 500]

def load_csv(path):
    with open(path) as f: rows=list(csv.DictReader(f))
    return np.array([float(r["L"]) for r in rows])/1e3, np.array([float(r["runtime"]) for r in rows])/1e6

hw_ms = 895.65

fig = plt.figure(figsize=(2.83, 1.62))
gs = fig.add_gridspec(2, 1, height_ratios=[2.5, 1], hspace=0.08)
ax_top = fig.add_subplot(gs[0])
ax_bot = fig.add_subplot(gs[1], sharex=ax_top)
plt.setp(ax_top.get_xticklabels(), visible=False)

for ax in [ax_top, ax_bot]:
    for lo, hi, color, alpha in ZONE_COLORS:
        ax.axvspan(lo, hi, color=color, alpha=alpha, zorder=0, linewidth=0)
    for b in ZONE_BOUNDARIES:
        ax.axvline(x=b, color="#AAAAAA", ls="-", lw=0.4, alpha=0.6, zorder=1)

L_m, T_m = load_csv(ROOT/"output/llama7b/partial_100pct/sweeps/full_runtime.csv")
ax_top.plot(L_m, T_m, color=C_MONO, ls="-", lw=1.6, zorder=3)

L_c, T_c = load_csv(ROOT/"output/llama7b/comp_100pct/sweeps/composed_runtime.csv")
ax_top.plot(L_c, T_c, color=C_COMP, ls="-", lw=1.6, zorder=3)

lgs_L = np.array([0, 25, 50, 100, 200, 500, 1000], dtype=float)
lgs_T = np.array([880.8, 896.1, 912.7, 946.2, 1016.2, 1163.6, 1600.0])
ax_top.plot(lgs_L, lgs_T, "s-.", color=C_LGS, lw=1.2, ms=3, zorder=3)

ax_top.errorbar(4.0, hw_ms, fmt="*", color=C_HW, ms=7, capsize=3, capthick=1, elinewidth=1, zorder=10, clip_on=False)

# Inline annotations on each line
ax_top.annotate("Monolithic LP\n83 min, 13.7 GB", xy=(910, 750),
                fontsize=6, color=C_MONO, ha="right", va="bottom",
                xytext=(-5, 4), textcoords="offset points")

ax_top.annotate("Composite LP\n1.3 min, 343 MB", xy=(65, 850),
                fontsize=6, color=C_COMP, ha="left", va="top",
                xytext=(-5, -4), textcoords="offset points")

ax_top.annotate("LGS\n9.7 min, 482 MB", xy=(195, 1640),
                fontsize=6, color=C_LGS, ha="left", va="top",
                xytext=(5, -4), textcoords="offset points")

ax_top.annotate("Measured", xy=(0.0, hw_ms + 349),
                fontsize=6, color=C_HW, ha="left", va="top",
                xytext=(2, -2), textcoords="offset points")

ax_top.set_ylabel("$T(L)$ [ms]")
ax_top.set_ylim(bottom=0)
ax_top.set_xlim(0, 1000)
ax_top.grid(True, linestyle=":")

# Lambda panel
dx = np.diff(L_c); dy = np.diff(T_c)
s = np.where(dx > 0, dy / dx, 0)
xm = (L_c[:-1] + L_c[1:]) / 2
ax_bot.plot(xm, s * 1e3, color=C_COMP, ls="-", lw=1.0, zorder=3)
ax_bot.set_xlabel("$L$ [$\\mu$s]")
ax_bot.set_ylabel("$\\lambda_L$")
ax_bot.set_xlim(0, 1000)
ax_bot.grid(True, linestyle=":")

fig.savefig(OUT/"fig5_llama7b.pdf"); fig.savefig(OUT/"fig5_llama7b.png", dpi=300)
print(f"Saved {OUT/'fig5_llama7b.pdf'}")
plt.close()
