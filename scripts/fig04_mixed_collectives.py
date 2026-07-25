#!/usr/bin/env python3
import csv, matplotlib; matplotlib.use("Agg")
import os
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from pathlib import Path
from matplotlib.offsetbox import HPacker, TextArea, AnchoredOffsetbox, VPacker

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "output/final_plots/data/mixed_16n_ch1"
FULL_RUN = os.environ.get("SC26_FULL_RUN") == "1"

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

def load_csv(p):
    if not p.exists(): return np.array([]),np.array([])
    with open(p) as f: rows=list(csv.DictReader(f))
    k=list(rows[0].keys())
    return np.array([float(r[k[0]]) for r in rows]),np.array([float(r[k[1]]) for r in rows])

ci=pd.read_csv(DATA/"collective_instances.csv")
walls=[(ci[ci['goal_rank']==r].sort_values('start')['end'].max()-ci[ci['goal_rank']==r].sort_values('start')['start'].min())/1e6 for r in ci['goal_rank'].unique()]
hw_m,hw_lo,hw_hi=np.mean(walls),np.min(walls),np.max(walls)
hw_err=[[hw_m-hw_lo],[hw_hi-hw_m]]

full_L,full_T=load_csv(DATA/"latency_full_runtime.csv")
comp_L,comp_T=load_csv(DATA/"latency_composite_runtime.csv")
if not len(comp_L):
    comp_L,comp_T=full_L,full_T
lgs_L,lgs_T=load_csv(DATA/"latency_lgs_runtime.csv")

fig=plt.figure(figsize=(2.83,1.62))
gs=fig.add_gridspec(2,1,height_ratios=[2.5,1],hspace=0.08)
ax_top=fig.add_subplot(gs[0]); ax_bot=fig.add_subplot(gs[1],sharex=ax_top)
plt.setp(ax_top.get_xticklabels(),visible=False)

for ax in [ax_top, ax_bot]:
    for lo, hi, color, alpha in ZONE_COLORS:
        ax.axvspan(lo, hi, color=color, alpha=alpha, zorder=0, linewidth=0)
    for b in ZONE_BOUNDARIES:
        ax.axvline(x=b, color="#AAAAAA", ls="-", lw=0.4, alpha=0.6, zorder=1)

if len(full_L):
    ax_top.plot(full_L/1e3,full_T/1e6,color=C_MONO,ls="-",lw=1.6,label="Monolithic LP", zorder=3)
ax_top.plot(comp_L/1e3,comp_T/1e6,color=C_COMP,ls="-",lw=1.6,label="Composite LP", zorder=3)
ax_top.plot(lgs_L/1e3,lgs_T/1e6,"s:",color=C_LGS,lw=1.2,ms=3,label="LGS", zorder=3)
ax_top.errorbar(4.0,hw_m,yerr=hw_err,fmt="*",color=C_HW,ms=7,capsize=3,capthick=1,elinewidth=1,zorder=5)
ax_top.plot([],[],"*",color=C_HW,ms=7,label="Measured")

if not FULL_RUN:
    FS = 6
    line1_parts = [
        TextArea("Monolithic LP", textprops=dict(fontsize=FS, fontstyle="italic", color=C_MONO)),
        TextArea(" and", textprops=dict(fontsize=FS, fontstyle="italic", color="black")),
    ]
    line2_parts = [
        TextArea("Composite LP", textprops=dict(fontsize=FS, fontstyle="italic", color=C_COMP)),
        TextArea(" overlap", textprops=dict(fontsize=FS, fontstyle="italic", color="black")),
    ]
    row1 = HPacker(children=line1_parts, pad=0, sep=1, align="baseline")
    row2 = HPacker(children=line2_parts, pad=0, sep=1, align="baseline")
    box = VPacker(children=[row1, row2], pad=0, sep=1, align="left")
    ab = AnchoredOffsetbox(loc="lower right", child=box, pad=0.3, frameon=False,
                           bbox_to_anchor=(0.98, 0.3), bbox_transform=ax_top.transAxes)
    ax_top.add_artist(ab)

ax_top.set_ylabel("$T(L)$ [ms]"); ax_top.set_ylim(bottom=0)
ax_top.set_xlim(0, 1000)
ax_top.legend(loc="upper left",framealpha=0.9,borderpad=0.3,handlelength=1.5)
ax_top.grid(True,linestyle=":")

dx=np.diff(comp_L/1e3); dy=np.diff(comp_T/1e6)
s=np.where(dx>0,dy/dx,0); xm=(comp_L[:-1]+comp_L[1:])/2e3
ax_bot.plot(xm,s*1e3,color=C_COMP,ls="-",lw=1.0, zorder=3)
ax_bot.set_xlabel("$L$ [$\\mu$s]"); ax_bot.set_ylabel("$\\lambda_L$")
ax_bot.set_xlim(0, 1000)
ax_bot.grid(True,linestyle=":")

fig.savefig(OUT/"fig_mixed_16n_ch1.pdf"); fig.savefig(OUT/"fig_mixed_16n_ch1.png",dpi=300)
print(f"Saved {OUT/'fig_mixed_16n_ch1.pdf'}"); plt.close()
