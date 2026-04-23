#!/usr/bin/env python3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from pathlib import Path

COLORED_REGION_ALPHA = 0.06

LAT_DATA = [
    (0, 862.9151),
    (400, 861.8723), (2484, 867.1323), (4568, 865.5315), (6653, 864.6670),
    (8737, 861.1290), (10821, 861.4144), (12905, 860.8533), (14989, 868.1283),
    (17074, 866.1225), (19158, 867.3351), (21242, 861.6699), (23326, 870.1773),
    (25411, 869.2742), (27495, 864.1874), (29579, 864.2086), (31663, 864.5080),
    (33747, 865.8420), (35832, 868.0417), (37916, 867.5226), (40000, 866.5870),
    (50000, 869.7151), (60000, 871.6429), (70000, 874.2429),
    (80000, 876.8429), (90000, 879.4763), (100000, 899.4183), (110000, 921.8583),
    (120000, 944.4062), (130000, 967.9264), (140000, 991.6064), (150000, 1015.2864),
    (160000, 1038.9664), (170000, 1062.6464), (180000, 1086.3264), (190000, 1110.0064),
    (200000, 1142.0717), (210000, 1185.5917), (220000, 1229.1117), (230000, 1272.6317),
    (240000, 1316.1517), (250000, 1359.6717), (260000, 1403.1917), (270000, 1446.7117),
    (280000, 1490.2317), (290000, 1533.7517), (300000, 1577.2717), (310000, 1620.7917),
    (320000, 1664.3117), (330000, 1707.8317), (340000, 1751.3517), (350000, 1794.8717),
    (360000, 1838.3917), (370000, 1881.9117), (380000, 1925.4317), (390000, 1968.9517),
    (400000, 2012.4717), (410000, 2055.9917), (420000, 2099.5117), (430000, 2143.0317),
    (440000, 2186.5517), (450000, 2230.0717), (460000, 2273.5917), (470000, 2317.1117),
    (480000, 2360.6317), (490000, 2404.1517), (500000, 2447.6717), (510000, 2491.1917),
    (520000, 2534.7117), (530000, 2578.2317), (540000, 2621.7517), (550000, 2665.2717),
    (560000, 2708.7917), (570000, 2752.3117), (580000, 2795.8317), (590000, 2839.3517),
    (600000, 2882.8717), (610000, 2926.3917), (620000, 2969.9117), (630000, 3013.4317),
    (640000, 3056.9517), (650000, 3100.4717), (660000, 3143.9917), (670000, 3187.5117),
    (680000, 3231.0317), (690000, 3274.5517), (700000, 3318.0717), (710000, 3361.5917),
    (720000, 3405.1117), (730000, 3448.6317), (740000, 3492.1517), (750000, 3535.6717),
    (760000, 3579.1917), (770000, 3622.7117), (780000, 3666.2317), (790000, 3709.7517),
    (800000, 3753.2717), (810000, 3796.7917), (820000, 3840.3117), (830000, 3883.8317),
    (840000, 3927.3517), (850000, 3970.8717), (860000, 4014.3917), (870000, 4057.9117),
    (880000, 4101.4317), (890000, 4144.9517), (900000, 4188.4717), (910000, 4231.9917),
    (920000, 4275.5117), (930000, 4319.0317), (940000, 4362.5517), (950000, 4406.0717),
    (960000, 4449.5917), (970000, 4493.1117), (980000, 4536.6317), (990000, 4580.1517),
    (1000000, 4623.6717),
]

BW_DATA = [
    (10.0, 16107.0129), (13.1, 12345.6245), (17.1, 9465.9641), (22.3, 7261.3481),
    (29.1, 5573.5213), (38.0, 4281.3410), (49.7, 3292.0818), (64.9, 2534.6967),
    (84.7, 1954.8590), (110.7, 1510.9438), (144.6, 1171.0967), (188.8, 910.9095),
    (246.6, 711.7205), (322.2, 559.2181), (420.8, 442.4560), (549.7, 353.0884),
    (718.0, 285.2548), (937.8, 246.3660), (1224.9, 230.6610), (1600.0, 229.4248),
]

TIER_BW_GBPS = np.array([100, 200, 400, 800, 1600])
TIER_COST_M = np.array([4, 12, 24, 36, 66])

L_ALPS = 4000
BW_ALPS = 200

plt.rcParams.update({
    "font.size": 8,
    "axes.labelsize": 8.5,
    "axes.titlesize": 9,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "lines.linewidth": 2.0,
    "axes.linewidth": 0.7,
    "grid.linewidth": 0.35,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})


def plot_lat_bw_impact(ax):
    lat_L = np.array([d[0] for d in LAT_DATA])
    lat_T = np.array([d[1] for d in LAT_DATA])
    lat_mask = lat_L > 0
    lat_L = lat_L[lat_mask]
    lat_T = lat_T[lat_mask]
    lat_scale = L_ALPS / lat_L

    bw_gbps = np.array([d[0] for d in BW_DATA])
    bw_T = np.array([d[1] for d in BW_DATA])
    bw_scale = bw_gbps / BW_ALPS

    lat_baseline_T = np.interp(L_ALPS, lat_L, lat_T)
    bw_baseline_T = np.interp(BW_ALPS, bw_gbps, bw_T)
    lat_rel_perf = lat_baseline_T / lat_T
    bw_rel_perf = bw_baseline_T / bw_T

    bw_sort = np.argsort(bw_scale)
    bw_scale_ext = np.append([0.1], bw_scale[bw_sort])
    bw_rel_perf_ext = np.append([bw_rel_perf[bw_sort][0]], bw_rel_perf[bw_sort])

    ax.axvspan(0.1, 1.0, alpha=COLORED_REGION_ALPHA, color="#B71C1C", zorder=0)
    ax.axvspan(1.0, 10.0, alpha=COLORED_REGION_ALPHA, color="#2E7D32", zorder=0)
    ax.plot(bw_scale_ext, bw_rel_perf_ext, color="#C0392B", label="Changing Bandwidth")
    ax.plot(lat_scale, lat_rel_perf, color="#2C3E50", label="Changing Latency")
    ax.axvline(x=1.0, color="gray", ls="--", alpha=0.5, lw=0.8)
    ax.axhline(y=1.0, color="gray", ls="--", alpha=0.5, lw=0.8)

    ax.set_xscale("log")
    ax.set_xlim(0.1, 10)
    ax.set_ylim(0, max(np.max(lat_rel_perf), np.max(bw_rel_perf_ext)) * 1.05)

    scale_ticks = [0.1, 0.2, 0.5, 1, 2, 5, 10]
    ax.set_xticks(scale_ticks)
    ax.set_xticklabels([f"{s}x" for s in scale_ticks])

    def fmt_bw(scale):
        bw = BW_ALPS * scale
        if bw >= 1000:
            return f"{bw / 1000:.1f}Tbps"
        return f"{bw:.0f}Gbps"

    bw_abs = [fmt_bw(scale) for scale in scale_ticks]
    lat_abs = [f"{L_ALPS / scale / 1000:.1f}μs" if L_ALPS / scale / 1000 < 10 else f"{L_ALPS / scale / 1000:.0f}μs" for scale in scale_ticks]

    for scale, bw_label in zip(scale_ticks, bw_abs):
        ax.annotate(
            bw_label,
            xy=(scale, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -18),
            textcoords="offset points",
            ha="center",
            fontsize=6,
            color="#C0392B",
        )

    for scale, lat_label in zip(scale_ticks, lat_abs):
        ax.annotate(
            lat_label,
            xy=(scale, 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -24),
            textcoords="offset points",
            ha="center",
            fontsize=6,
            color="#2C3E50",
        )

    ax.annotate(
        "$\\leftarrow$ Worse L or BW",
        xy=(0.06, 0.32),
        xycoords="axes fraction",
        fontsize=8,
        color="#B71C1C",
        fontstyle="italic",
        alpha=0.7,
        fontweight="bold",
    )
    ax.annotate(
        "Better L or BW $\\rightarrow$",
        xy=(0.65, 0.32),
        xycoords="axes fraction",
        fontsize=8,
        color="#2E7D32",
        fontstyle="italic",
        alpha=0.7,
        fontweight="bold",
    )
    # ax.text(
    #     0.5,
    #     0.93,
    #     "Llama 70B (32 Nodes, 128 GPUs)",
    #     transform=ax.transAxes,
    #     ha="center",
    #     va="top",
    #     fontsize=8,
    #     fontweight="bold",
    #     color="#222",
    #     bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.8),
    # )
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, linestyle=":", which="both")
    ax.set_xlabel("Scaling factor (1x = Alps settings)", labelpad=12)


def plot_cost_perf_pareto(ax):
    bw_gbps = np.array([d[0] for d in BW_DATA])
    bw_T_s = np.array([d[1] for d in BW_DATA]) / 1e3

    bw_baseline_T_s = np.interp(BW_ALPS, bw_gbps, bw_T_s)
    runtime_at_tier = np.interp(TIER_BW_GBPS, bw_gbps, bw_T_s)
    bw_dense = np.linspace(50, 1600, 500)
    runtime_dense = np.interp(bw_dense, bw_gbps, bw_T_s)
    cost_dense = np.interp(bw_dense, TIER_BW_GBPS, TIER_COST_M)
    rel_perf_at_tier = bw_baseline_T_s / runtime_at_tier
    rel_perf_dense = bw_baseline_T_s / runtime_dense

    hw_cost = np.interp(BW_ALPS, TIER_BW_GBPS, TIER_COST_M)
    baseline_idx = int(np.where(TIER_BW_GBPS == BW_ALPS)[0][0])
    tier_costs_no_baseline = np.delete(TIER_COST_M, baseline_idx)
    tier_perf_no_baseline = np.delete(rel_perf_at_tier, baseline_idx)
    tier_bw_no_baseline = np.delete(TIER_BW_GBPS, baseline_idx)

    ax.plot(cost_dense, rel_perf_dense, color="#C0392B", ls="-", lw=1.8, zorder=3)
    ax.plot(
        tier_costs_no_baseline,
        tier_perf_no_baseline,
        "D",
        color="#C0392B",
        ms=6.2,
        mec="white",
        mew=0.5,
        zorder=5,
    )

    for bw, cost, rel_perf in zip(tier_bw_no_baseline, tier_costs_no_baseline, tier_perf_no_baseline):
        if bw == 1600:
            offset_x, offset_y, ha = -4, -10, "right"
            kw = {}
        elif bw == 800:
            offset_x, offset_y, ha = 0, -14, "center"
            kw = {}
        elif bw == 100:
            offset_x, offset_y, ha = -15, 5, "left"
            kw = {}
        elif bw == 400:
            offset_x, offset_y, ha = 7, 0, "left"
            kw = {}
        else:
            offset_x, offset_y, ha = 5, 6, "left"
            kw = {}
        ax.annotate(
            f"{bw} Gbps",
            (cost, rel_perf),
            textcoords="offset points",
            xytext=(offset_x, offset_y),
            fontsize=6,
            color="#333",
            fontweight="bold",
            ha=ha,
            **kw,
        )

    ax.plot(hw_cost, 1.0, "*", color="black", ms=9, zorder=6)
    ax.annotate(
        "Alps Baseline\n(200 Gbps)",
        xy=(hw_cost, 1.1),
        xytext=(-20, 3),
        textcoords="offset points",
        fontsize=6,
        color="black",
        fontweight="bold",
        ha="center",
        va="bottom",
    )

    # ax.axvspan(TIER_COST_M[0], TIER_COST_M[2], alpha=0.07, color="#2E7D32", zorder=0)
    ax.axvspan(-1, TIER_COST_M[3], alpha=COLORED_REGION_ALPHA, color="#2E7D32", zorder=0)
    ax.text(3, 2.4, "High value upgrades", fontsize=8, fontstyle="italic", color="#2E7D32", alpha=0.7, fontweight="bold")
    # ax.axvspan(TIER_COST_M[2], TIER_COST_M[-1], alpha=0.07, color="#B71C1C", zorder=0)
    ax.axvspan(TIER_COST_M[3], 100, alpha=COLORED_REGION_ALPHA, color="#B71C1C", zorder=0)
    ax.text(43, 2.4, "Diminishing returns", fontsize=8, fontstyle="italic", color="#B71C1C", alpha=0.7, fontweight="bold")

    ax.set_xlabel("Est. network-only cost [$M] (4K GPU fat-tree, fixed GPU config)")
    ax.set_ylim(min(np.min(rel_perf_dense), np.min(rel_perf_at_tier)) * 0.95, max(np.max(rel_perf_dense), np.max(rel_perf_at_tier)) * 1.05)
    ax.set_xlim(0, 70)
    ax.grid(True, linestyle=":")
    ax.axhline(y=1.0, color="gray", ls="--", alpha=0.5, lw=0.8)
    # ax.text(
    #     0.5,
    #     0.93,
    #     "Llama 70B (4096 GPUs)",
    #     transform=ax.transAxes,
    #     ha="center",
    #     va="top",
    #     fontsize=8,
    #     fontweight="bold",
    #     color="#222",
    #     bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.8),
    # )


def main():
    fig, (ax_top, ax_bottom) = plt.subplots(
        2, 1, figsize=(5, 3.3), gridspec_kw={"hspace": 0.6, "height_ratios": [0.9, 1.1]}
    )

    plot_lat_bw_impact(ax_top)
    plot_cost_perf_pareto(ax_bottom)
    fig.supylabel("Relative Performance vs Alps Baseline", x=0.05, fontsize=10)
    # fig.add_artist(
    #     Line2D([0.12, 0.98], [0.50, 0.50], transform=fig.transFigure, color="#9A9A9A", lw=0.6, alpha=0.8)
    # )

    plt.show()
    out_dir = Path(__file__).resolve().parents[1] / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig_network_perf_combined.pdf")
    fig.savefig(out_dir / "fig_network_perf_combined.png", dpi=300)
    print("Saved fig_network_perf_combined.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
