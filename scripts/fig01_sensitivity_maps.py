#!/usr/bin/env python3
"""
Build derived 2D latency/bandwidth sensitivity maps from the existing 1D sweeps.

This is intentionally a phase-diagram style view, not a true joint 2D sweep:
for each workload, we compare the relative slowdown induced by latency and by
bandwidth separately, anchored to that workload's operating-point baseline,
then classify each (L, BW) point into four effect regions:

  - near baseline (+/-5%)
  - latency-dominated
  - bandwidth-dominated
  - both matter

Outputs:
  - fig_2d_sensitivity_llama_detail.{pdf,png}
  - fig_2d_sensitivity_workloads.{pdf,png}
  - fig_2d_sensitivity_frontiers.{pdf,png}
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from matplotlib import colors as mcolors
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.ticker import FuncFormatter
from matplotlib.lines import Line2D
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("SC26_DATA_ROOT", ART_ROOT / "data"))
OUT = Path(os.environ.get("SC26_FIGURE_DIR", ART_ROOT / "figures"))
ASSETS = ART_ROOT / "scripts" / "assets"
VARIANT_OUT = OUT / "palette_variants"
OUT.mkdir(parents=True, exist_ok=True)
VARIANT_OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 7,
    "axes.labelsize": 6.8,
    "axes.titlesize": 7.2,
    "legend.fontsize": 5.2,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "lines.linewidth": 1.4,
    "axes.linewidth": 0.6,
    "grid.linewidth": 0.3,
    "grid.alpha": 0.25,
    "figure.dpi": 300,
    "pdf.compression": 9,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})

LAT_MAX_US = 1000.0
LAT_MIN_US = 1.0
BW_MIN_GBPS = 10.0
BW_MAX_GBPS = 1600.0
L_GRID = np.geomspace(LAT_MIN_US, LAT_MAX_US, 321)
BW_GRID = np.geomspace(BW_MIN_GBPS, BW_MAX_GBPS, 241)

NEAR_BASELINE_THRESHOLD = 0.05
DOMINANCE_RATIO = 1.8
DEFAULT_LAT_BASELINE_US = 4.0
CHANGE_SHADE_LEVELS = [0.25, 0.50, 1.00]
CHANGE_BAND_LABELS = ["0-25%", "25-50%", "50-100%", ">100%"]
CHANGE_BAND_COLORS = ["#F1F4F6", "#DDE4EA", "#C2CBD4", "#9CA8B3"]
CONTOUR_LEVEL_SPECS = [
    (0.05, "#59616A", "-", 1.05),
    (0.25, "#6F7984", "--", 0.90),
    (0.50, "#88939E", "-.", 0.82),
    (1.00, "#A5AFB8", ":", 1.02),
]

PHASE_LIGHT_COLORS = {
    "Near baseline (+/-5%)": "#EEF3EC",
    "Latency-dominated": "#F6EFE4",
    "Bandwidth-dominated": "#E8EEF6",
    "Both matter": "#F2EBF0",
}
PHASE_DARK_COLORS = {
    "Near baseline (+/-5%)": "#C4D2C2",
    "Latency-dominated": "#D1B287",
    "Bandwidth-dominated": "#88A3C4",
    "Both matter": "#B99DAA",
}
PHASE_ORDER = [
    "Near baseline (+/-5%)",
    "Latency-dominated",
    "Bandwidth-dominated",
    "Both matter",
]
PHASE_TO_ID = {name: idx for idx, name in enumerate(PHASE_ORDER)}


def make_phase_colors(phase_light_colors, phase_dark_colors):
    return {
        name: tuple(
            np.array(mcolors.to_rgb(phase_light_colors[name])) * 0.45
            + np.array(mcolors.to_rgb(phase_dark_colors[name])) * 0.55
        )
        for name in PHASE_ORDER
    }


PHASE_COLORS = make_phase_colors(PHASE_LIGHT_COLORS, PHASE_DARK_COLORS)

PALETTE_VARIANTS = {
    "01_current_soft": {
        "label": "Current soft",
        "light": {
            "Near baseline (+/-5%)": "#EEF3EC",
            "Latency-dominated": "#F6EFE4",
            "Bandwidth-dominated": "#E8EEF6",
            "Both matter": "#F2EBF0",
        },
        "dark": {
            "Near baseline (+/-5%)": "#C4D2C2",
            "Latency-dominated": "#D1B287",
            "Bandwidth-dominated": "#88A3C4",
            "Both matter": "#B99DAA",
        },
    },
    "02_editorial_muted": {
        "label": "Editorial muted",
        "light": {
            "Near baseline (+/-5%)": "#EEF2EC",
            "Latency-dominated": "#F4EBDD",
            "Bandwidth-dominated": "#E7EEF6",
            "Both matter": "#F0E7EC",
        },
        "dark": {
            "Near baseline (+/-5%)": "#C2CEC1",
            "Latency-dominated": "#D0B28A",
            "Bandwidth-dominated": "#8EA8C5",
            "Both matter": "#B79DA9",
        },
    },
    "03_neutral_minimal": {
        "label": "Neutral minimal",
        "light": {
            "Near baseline (+/-5%)": "#F0F1EC",
            "Latency-dominated": "#F1E8DB",
            "Bandwidth-dominated": "#E9EDF2",
            "Both matter": "#EEE8E7",
        },
        "dark": {
            "Near baseline (+/-5%)": "#CBD0C6",
            "Latency-dominated": "#C7AF93",
            "Bandwidth-dominated": "#9AA9B8",
            "Both matter": "#B8ACAA",
        },
    },
    "04_richer_pastel": {
        "label": "Richer pastel",
        "light": {
            "Near baseline (+/-5%)": "#E7EFE8",
            "Latency-dominated": "#F3E2C8",
            "Bandwidth-dominated": "#DFEAF7",
            "Both matter": "#EADDE6",
        },
        "dark": {
            "Near baseline (+/-5%)": "#B8CBB9",
            "Latency-dominated": "#C9A87C",
            "Bandwidth-dominated": "#7E9EC4",
            "Both matter": "#AD8FA0",
        },
    },
    "05_terracotta_teal": {
        "label": "Terracotta teal",
        "light": {
            "Near baseline (+/-5%)": "#F2EFE8",
            "Latency-dominated": "#F2DED4",
            "Bandwidth-dominated": "#DCEFED",
            "Both matter": "#E9DFE7",
        },
        "dark": {
            "Near baseline (+/-5%)": "#CCC4B6",
            "Latency-dominated": "#C56F56",
            "Bandwidth-dominated": "#4E948A",
            "Both matter": "#8F6B88",
        },
    },
    "06_blueprint_ochre": {
        "label": "Blueprint ochre",
        "light": {
            "Near baseline (+/-5%)": "#EEF1E8",
            "Latency-dominated": "#F3E7D0",
            "Bandwidth-dominated": "#DFE9F7",
            "Both matter": "#ECDDE0",
        },
        "dark": {
            "Near baseline (+/-5%)": "#C0C8B8",
            "Latency-dominated": "#C29A54",
            "Bandwidth-dominated": "#547DAF",
            "Both matter": "#A66D79",
        },
    },
    "07_modernist_ink": {
        "label": "Modernist ink",
        "light": {
            "Near baseline (+/-5%)": "#F3EEE6",
            "Latency-dominated": "#F1D9C7",
            "Bandwidth-dominated": "#DCEBF0",
            "Both matter": "#E5D9E8",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D2C3B1",
            "Latency-dominated": "#C4643D",
            "Bandwidth-dominated": "#2F728C",
            "Both matter": "#7B4F8A",
        },
    },
    "08_ink_and_amber": {
        "label": "Ink and amber",
        "light": {
            "Near baseline (+/-5%)": "#EDF0EB",
            "Latency-dominated": "#F3E3C9",
            "Bandwidth-dominated": "#DDEBF0",
            "Both matter": "#E7DFEA",
        },
        "dark": {
            "Near baseline (+/-5%)": "#BEC6BB",
            "Latency-dominated": "#BE8A32",
            "Bandwidth-dominated": "#3B7A88",
            "Both matter": "#81638C",
        },
    },
    "09_powder_room": {
        "label": "Powder room",
        "light": {
            "Near baseline (+/-5%)": "#F2F4EF",
            "Latency-dominated": "#F5ECE4",
            "Bandwidth-dominated": "#EAF1F6",
            "Both matter": "#F0EAF0",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D5DBCF",
            "Latency-dominated": "#DCC2AF",
            "Bandwidth-dominated": "#B6C8D8",
            "Both matter": "#CBB8C7",
        },
    },
    "10_sage_blush": {
        "label": "Sage blush",
        "light": {
            "Near baseline (+/-5%)": "#EEF3EE",
            "Latency-dominated": "#F4ECE5",
            "Bandwidth-dominated": "#E7EEF3",
            "Both matter": "#F1EAEE",
        },
        "dark": {
            "Near baseline (+/-5%)": "#C9D5CA",
            "Latency-dominated": "#D9C4B6",
            "Bandwidth-dominated": "#AFC2D2",
            "Both matter": "#C8B5BF",
        },
    },
    "11_misty_harbor": {
        "label": "Misty harbor",
        "light": {
            "Near baseline (+/-5%)": "#F0F3F0",
            "Latency-dominated": "#F3ECE2",
            "Bandwidth-dominated": "#E8EFF4",
            "Both matter": "#EEE8EE",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D1D8D0",
            "Latency-dominated": "#D5C1AE",
            "Bandwidth-dominated": "#A8BECE",
            "Both matter": "#C4B6C5",
        },
    },
    "12_chalk_garden": {
        "label": "Chalk garden",
        "light": {
            "Near baseline (+/-5%)": "#F1F4EE",
            "Latency-dominated": "#F5EEE3",
            "Bandwidth-dominated": "#EAF0F6",
            "Both matter": "#F0EBEF",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D4DCCF",
            "Latency-dominated": "#D8C7B2",
            "Bandwidth-dominated": "#B3C4D4",
            "Both matter": "#CBBCC6",
        },
    },
    "13_seafoam_apricot": {
        "label": "Seafoam apricot",
        "light": {
            "Near baseline (+/-5%)": "#F4F0E8",
            "Latency-dominated": "#F6E5DA",
            "Bandwidth-dominated": "#E3F1EA",
            "Both matter": "#ECE7F2",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D8CEC0",
            "Latency-dominated": "#D9B8A1",
            "Bandwidth-dominated": "#A9C9BA",
            "Both matter": "#BBAFCA",
        },
    },
    "14_lilac_sand": {
        "label": "Lilac sand",
        "light": {
            "Near baseline (+/-5%)": "#F1F1EC",
            "Latency-dominated": "#F3EADB",
            "Bandwidth-dominated": "#EAE6F4",
            "Both matter": "#EDE3E7",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D1D2C7",
            "Latency-dominated": "#D3C0A7",
            "Bandwidth-dominated": "#B8B0D2",
            "Both matter": "#C6B0B8",
        },
    },
    "15_rose_mint": {
        "label": "Rose mint",
        "light": {
            "Near baseline (+/-5%)": "#F3F0EC",
            "Latency-dominated": "#F4E1E6",
            "Bandwidth-dominated": "#E4F1EC",
            "Both matter": "#E5E8F2",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D6CCC5",
            "Latency-dominated": "#D2AFB8",
            "Bandwidth-dominated": "#A9C7BC",
            "Both matter": "#AEB7CF",
        },
    },
    "16_butter_teal": {
        "label": "Butter teal",
        "light": {
            "Near baseline (+/-5%)": "#F1F2EF",
            "Latency-dominated": "#F3ECD6",
            "Bandwidth-dominated": "#E5EFF0",
            "Both matter": "#EEE5EF",
        },
        "dark": {
            "Near baseline (+/-5%)": "#D0D4CD",
            "Latency-dominated": "#D4C197",
            "Bandwidth-dominated": "#A9C0C2",
            "Both matter": "#C2B0C4",
        },
    },
}

WORKLOAD_COLORS = {
    "Llama (128 GPUs)": "#8A6255",
    "Grok (4096 GPUs)": "#5A7B99",
    "vLLM (8 GPUs)": "#6D8A7C",
}

LOGO_PATHS = {
    "cscs": ASSETS / "cscs_mark.png",
    "azure": ASSETS / "azure_mark.png",
}
LOGO_ZOOMS = {
    "cscs": 0.0485,
    "azure": 0.05185,
}
LOGO_CACHE = {}


def load_llama_curves():
    lat_df = pd.read_csv(
        ROOT / "workspaces" / "llama7b_n32_spcl_20260407" / "output" / "comp" / "sweeps" / "composed_runtime.csv"
    )
    bw_df = pd.read_csv(
        ROOT / "workspaces" / "llama7b_n32_spcl_20260407" / "output" / "bw_sensitivity_l4us_composition_exact_goal" / "bandwidth_sensitivity.csv"
    )
    lat_us = lat_df["L"].to_numpy(dtype=float) / 1e3
    lat_runtime_s = lat_df["runtime"].to_numpy(dtype=float) / 1e9
    bw_gbps = bw_df["bw_gbps"].to_numpy(dtype=float)
    bw_runtime_s = bw_df["runtime_ns"].to_numpy(dtype=float) / 1e9
    return lat_us, lat_runtime_s, bw_gbps, bw_runtime_s


def load_grok_curves():
    lat_df = pd.read_csv(ROOT / "output" / "grok_final" / "grok_N1024_latency_sweep.csv")
    bw_df = pd.read_csv(ROOT / "output" / "grok_final" / "grok_N1024_bw_sweep.csv")
    lat_us = lat_df["L_us"].to_numpy(dtype=float)
    lat_runtime_s = lat_df["runtime_s"].to_numpy(dtype=float)
    bw_gbps = bw_df["bw_gbps"].to_numpy(dtype=float)
    bw_runtime_s = bw_df["runtime_s"].to_numpy(dtype=float)
    return lat_us, lat_runtime_s, bw_gbps, bw_runtime_s


def load_vllm_curves():
    lat_df = pd.read_csv(ROOT / "output" / "vllm_llama8b_128tok" / "latency_runtime.csv")
    bw_df = pd.read_csv(ROOT / "output" / "vllm_llama8b_128tok" / "bandwidth_runtime.csv")

    lat_us = lat_df["L"].to_numpy(dtype=float) / 1e3
    lat_runtime_s = lat_df["runtime"].to_numpy(dtype=float) / 1e9

    g_ns_per_byte = bw_df["G"].to_numpy(dtype=float)
    bw_runtime_s = bw_df["runtime"].to_numpy(dtype=float) / 1e9
    mask = g_ns_per_byte > 0.0
    bw_gbps = 8.0 / g_ns_per_byte[mask]
    bw_runtime_s = bw_runtime_s[mask]
    order = np.argsort(bw_gbps)
    bw_gbps = bw_gbps[order]
    bw_runtime_s = bw_runtime_s[order]
    keep = (bw_gbps >= BW_MIN_GBPS) & (bw_gbps <= BW_MAX_GBPS)
    return lat_us, lat_runtime_s, bw_gbps[keep], bw_runtime_s[keep]


def monotonic_interp(x, y, grid):
    order = np.argsort(x)
    x_sorted = np.asarray(x, dtype=float)[order]
    y_sorted = np.asarray(y, dtype=float)[order]
    return np.interp(grid, x_sorted, y_sorted, left=y_sorted[0], right=y_sorted[-1])


def interp_scalar(x, y, target):
    order = np.argsort(x)
    x_sorted = np.asarray(x, dtype=float)[order]
    y_sorted = np.asarray(y, dtype=float)[order]
    return float(np.interp(target, x_sorted, y_sorted, left=y_sorted[0], right=y_sorted[-1]))


def relative_delta(curve, baseline_runtime, ref_runtime):
    return (curve - baseline_runtime) / ref_runtime


def banded_strength(values, boundaries, strengths):
    band_ids = np.digitize(values, boundaries, right=False)
    return np.take(np.asarray(strengths, dtype=float), band_ids)


def phase_shade_strength(phase_name, total_change):
    _ = phase_name
    return banded_strength(total_change, CHANGE_SHADE_LEVELS, [0.18, 0.42, 0.62, 0.82])


def build_phase_facecolors(classes, total_change, phase_light_colors=None, phase_dark_colors=None):
    phase_light_colors = phase_light_colors or PHASE_LIGHT_COLORS
    phase_dark_colors = phase_dark_colors or PHASE_DARK_COLORS
    facecolors = np.empty(classes.shape + (4,), dtype=float)
    for phase_name in PHASE_ORDER:
        phase_id = PHASE_TO_ID[phase_name]
        mask = classes == phase_id
        if not np.any(mask):
            continue
        light = np.array(mcolors.to_rgb(phase_light_colors[phase_name]))
        dark = np.array(mcolors.to_rgb(phase_dark_colors[phase_name]))
        strength = phase_shade_strength(phase_name, total_change)
        colors = light[None, None, :] * (1.0 - strength[..., None]) + dark[None, None, :] * strength[..., None]
        facecolors[..., :3][mask] = colors[mask]
    facecolors[..., 3] = 1.0
    return facecolors


def load_logo_image(logo_key):
    if logo_key not in LOGO_CACHE:
        logo = plt.imread(LOGO_PATHS[logo_key])
        if logo_key == "cscs":
            height, width = logo.shape[:2]
            compressed_height = max(1, int(round(height * 0.80)))
            row_idx = np.linspace(0, height - 1, compressed_height).round().astype(int)
            compressed = logo[row_idx]
            adjusted = np.zeros_like(logo)
            y0 = (height - compressed_height) // 2
            adjusted[y0:y0 + compressed_height, :, :] = compressed
            logo = adjusted
        LOGO_CACHE[logo_key] = logo
    return LOGO_CACHE[logo_key]


def add_runtime_change_contours(ax, workload, with_handles=False):
    handles = []
    for level, color, linestyle, linewidth in CONTOUR_LEVEL_SPECS:
        contour = safe_contour(
            ax,
            workload["total_change"],
            level,
            colors=color,
            linewidths=linewidth,
            linestyles=linestyle,
            zorder=4,
        )
        if contour is not None and with_handles:
            handles.append(Line2D([0], [0], color=color, lw=linewidth, ls=linestyle, label=f"{int(level * 100)}%"))
    return handles


def make_change_band_handles():
    return [
        Line2D(
            [0],
            [0],
            color=color,
            lw=linewidth,
            ls=linestyle,
            label=band_label,
        )
        for band_label, (level, color, linestyle, linewidth) in zip(
            CHANGE_BAND_LABELS, CONTOUR_LEVEL_SPECS
        )
    ]


def broadcast_surfaces(lat_curve, bw_curve):
    lat_surface = np.broadcast_to(lat_curve[None, :], (len(bw_curve), len(lat_curve)))
    bw_surface = np.broadcast_to(bw_curve[:, None], (len(bw_curve), len(lat_curve)))
    return lat_surface, bw_surface


def classify_regions(lat_surface, bw_surface, total_change):
    classes = np.full(lat_surface.shape, PHASE_TO_ID["Both matter"], dtype=int)

    near_baseline = total_change <= NEAR_BASELINE_THRESHOLD
    lat_dom = (~near_baseline) & (lat_surface >= DOMINANCE_RATIO * np.maximum(bw_surface, 1e-12))
    bw_dom = (~near_baseline) & (bw_surface >= DOMINANCE_RATIO * np.maximum(lat_surface, 1e-12))

    classes[near_baseline] = PHASE_TO_ID["Near baseline (+/-5%)"]
    classes[lat_dom] = PHASE_TO_ID["Latency-dominated"]
    classes[bw_dom] = PHASE_TO_ID["Bandwidth-dominated"]
    return classes


def prepare_workload(name, loader, lat_baseline_us, bw_baseline_gbps, system_label, logo_key, point_label):
    lat_us, lat_runtime_s, bw_gbps, bw_runtime_s = loader()
    lat_interp = monotonic_interp(lat_us, lat_runtime_s, L_GRID)
    bw_interp = monotonic_interp(bw_gbps, bw_runtime_s, BW_GRID)
    lat_baseline_runtime = interp_scalar(lat_us, lat_runtime_s, lat_baseline_us)
    bw_baseline_runtime = interp_scalar(bw_gbps, bw_runtime_s, bw_baseline_gbps)
    ref_runtime = 0.5 * (lat_baseline_runtime + bw_baseline_runtime)

    lat_delta = relative_delta(lat_interp, lat_baseline_runtime, ref_runtime)
    bw_delta = relative_delta(bw_interp, bw_baseline_runtime, ref_runtime)
    lat_effect = np.abs(lat_delta)
    bw_effect = np.abs(bw_delta)
    lat_delta_surface, bw_delta_surface = broadcast_surfaces(lat_delta, bw_delta)
    lat_effect_surface, bw_effect_surface = broadcast_surfaces(lat_effect, bw_effect)
    total_signed = lat_delta_surface + bw_delta_surface
    total_change = np.abs(total_signed)
    contrib_balance = lat_effect_surface - bw_effect_surface
    classes = classify_regions(lat_effect_surface, bw_effect_surface, total_change)
    eq_contrib_masked = np.ma.masked_where(total_change < NEAR_BASELINE_THRESHOLD, contrib_balance)
    return {
        "name": name,
        "system_label": system_label,
        "logo_key": logo_key,
        "point_label": point_label,
        "lat_baseline_us": lat_baseline_us,
        "bw_baseline_gbps": bw_baseline_gbps,
        "lat_baseline_runtime": lat_baseline_runtime,
        "bw_baseline_runtime": bw_baseline_runtime,
        "ref_runtime": ref_runtime,
        "lat_interp": lat_interp,
        "bw_interp": bw_interp,
        "lat_delta": lat_delta,
        "bw_delta": bw_delta,
        "lat_effect": lat_effect,
        "bw_effect": bw_effect,
        "classes": classes,
        "facecolors": build_phase_facecolors(classes, total_change),
        "total_change": total_change,
        "total_signed": total_signed,
        "contrib_balance": contrib_balance,
        "eq_contrib_masked": eq_contrib_masked,
    }


def add_operating_point_marker(
    ax,
    workload,
    annotate=False,
    point_size=0,
    point_facecolor="white",
    point_edgecolor=None,
    point_linewidth=1.0,
    label_fontsize=5.5,
):
    if point_size > 0:
        ax.scatter(
            [workload["lat_baseline_us"]],
            [workload["bw_baseline_gbps"]],
            s=point_size,
            marker="o",
            facecolor=point_facecolor,
            edgecolors=point_edgecolor or WORKLOAD_COLORS.get(workload["name"], "#596067"),
            linewidths=point_linewidth,
            zorder=6,
            clip_on=False,
        )
    logo = load_logo_image(workload["logo_key"])
    ax.add_artist(
        AnnotationBbox(
            OffsetImage(logo, zoom=LOGO_ZOOMS[workload["logo_key"]]),
            (workload["lat_baseline_us"], workload["bw_baseline_gbps"]),
            xybox=(0, 0),
            xycoords="data",
            boxcoords="offset points",
            frameon=False,
            box_alignment=(0.5, 0.5),
            zorder=7,
            annotation_clip=False,
        )
    )
    if annotate:
        label_text = workload["point_label"]
        xytext = (0, -7 if "\n" in label_text else -6)
        ha = "center"
        va = "top"
        ax.annotate(
            label_text,
            xy=(workload["lat_baseline_us"], workload["bw_baseline_gbps"]),
            xytext=xytext,
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=label_fontsize,
            color="#28323A",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "#DDDDDD", "alpha": 0.92},
            zorder=10,
        )


def add_common_axes_style(ax):
    ax.set_xscale("log")
    ax.set_xlim(LAT_MIN_US, LAT_MAX_US)
    ax.set_yscale("log")
    ax.set_ylim(BW_MIN_GBPS, BW_MAX_GBPS)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])
    ax.set_yticks([10, 20, 50, 100, 200, 500, 1000, 1600])
    ax.xaxis.set_major_formatter(FuncFormatter(format_log_numeric_tick))
    ax.yaxis.set_major_formatter(FuncFormatter(format_log_numeric_tick))
    ax.grid(True, which="major", linestyle=":")
    ax.grid(True, which="minor", linestyle=":", alpha=0.10)
    ax.set_xlabel("Latency [$\\mu$s]")
    ax.set_ylabel("Bandwidth [Gbps]")


def format_workload_title(name):
    title_map = {
        "Llama (128 GPUs)": "Train. Llama, 128 GPUs",
        "Grok (4096 GPUs)": "Train. Grok, 4096 GPUs",
        "vLLM (8 GPUs)": "Infer. vLLM, 8 GPUs",
    }
    return title_map.get(name, name)


def format_log_numeric_tick(value, _pos):
    if value >= 100:
        return f"{int(round(value))}"
    if value >= 10:
        return f"{value:.0f}"
    if value >= 1:
        return f"{value:g}"
    return ""


def add_phase_legend(ax, loc="lower right"):
    handles = [
        mpatches.Patch(facecolor=PHASE_COLORS[name], edgecolor="none", label=name)
        for name in PHASE_ORDER
    ]
    ax.legend(handles=handles, loc=loc, framealpha=0.92, borderpad=0.3, handlelength=1.3)


def safe_contour(ax, field, level, **kwargs):
    if np.ma.isMaskedArray(field):
        values = field.compressed()
        if values.size == 0:
            return None
        vmin = float(np.min(values))
        vmax = float(np.max(values))
    else:
        vmin = float(np.min(field))
        vmax = float(np.max(field))
    if np.isclose(vmin, vmax):
        return None
    if not (vmin <= level <= vmax):
        return None
    zorder = kwargs.pop("zorder", None)
    contour = ax.contour(L_GRID, BW_GRID, field, levels=[level], **kwargs)
    if zorder is not None:
        if hasattr(contour, "set_zorder"):
            contour.set_zorder(zorder)
        if hasattr(contour, "collections"):
            for coll in contour.collections:
                coll.set_zorder(zorder)
    return contour


def make_llama_detail_figure(workload):
    fig, ax = plt.subplots(figsize=(4.8, 3.45))
    ax.pcolormesh(L_GRID, BW_GRID, workload["facecolors"], shading="nearest")
    add_common_axes_style(ax)
    ax.set_title("Llama (128 GPUs) — Derived 2D Latency/BW Regions", pad=4)
    add_operating_point_marker(ax, workload, annotate=True)

    line_legend_handles = add_runtime_change_contours(ax, workload, with_handles=True)

    phase_legend = ax.legend(
        handles=[
            mpatches.Patch(facecolor=PHASE_COLORS[name], edgecolor="none", label=name)
            for name in PHASE_ORDER
        ],
        loc="upper right",
        framealpha=0.92,
        borderpad=0.3,
        handlelength=1.3,
    )
    ax.text(
        0.98,
        0.02,
        (
            "Derived from separate 1D sweeps.\n"
            f"Anchored at L={workload['lat_baseline_us']:g} us, BW={workload['bw_baseline_gbps']:g} Gbps.\n"
            "Shades and contours indicate larger |total runtime change|."
        ),
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.3,
        color="#333333",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#DDDDDD", "alpha": 0.88},
    )

    if line_legend_handles:
        ax.add_artist(phase_legend)
        ax.legend(
            line_legend_handles,
            [f"{h.get_label()} total runtime change" for h in line_legend_handles],
            loc="lower left",
            framealpha=0.92,
            borderpad=0.3,
            handlelength=2.0,
        )

    for suffix in (".pdf", ".png"):
        out_path = OUT / f"fig_2d_sensitivity_llama_detail{suffix}"
        if suffix == ".png":
            fig.savefig(out_path, dpi=300)
        else:
            fig.savefig(out_path)
    plt.close(fig)


def make_workload_comparison_figure(
    workloads,
    output_dir=None,
    stem="fig_2d_sensitivity_workloads",
    phase_light_colors=None,
    phase_dark_colors=None,
):
    output_dir = output_dir or OUT
    output_dir.mkdir(parents=True, exist_ok=True)
    phase_light_colors = phase_light_colors or PHASE_LIGHT_COLORS
    phase_dark_colors = phase_dark_colors or PHASE_DARK_COLORS
    phase_colors = make_phase_colors(phase_light_colors, phase_dark_colors)
    outer_text_scale = 0.81
    inner_text_scale = 0.7425

    ncols = len(workloads)
    if ncols == 3:
        fig_width, fig_height = 3.50, 2.08
    elif ncols == 2:
        fig_width, fig_height = 2.42, 1.96
    else:
        fig_width, fig_height = 1.42, 1.84
    fig, axes = plt.subplots(1, ncols, figsize=(fig_width, fig_height), sharex=True, sharey=True)
    if ncols == 1:
        axes = [axes]
    fig.subplots_adjust(left=0.105, right=0.997, top=0.82, bottom=0.262, wspace=0.09)

    for ax, workload in zip(axes, workloads):
        ax.pcolormesh(
            L_GRID,
            BW_GRID,
            build_phase_facecolors(workload["classes"], workload["total_change"], phase_light_colors, phase_dark_colors),
            shading="nearest",
            rasterized=True,
            antialiased=False,
        )
        add_common_axes_style(ax)
        ax.set_box_aspect(1)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_xticks([1, 5, 20, 100, 500])
        ax.set_yticks([10, 50, 200, 1000])
        ax.tick_params(labelsize=5.7 * outer_text_scale, pad=1.2, length=2.9, width=0.6)
        ax.set_title(
            format_workload_title(workload["name"]),
            pad=1.5,
            fontsize=5.9 * outer_text_scale,
            linespacing=0.9,
        )
        add_operating_point_marker(
            ax,
            workload,
            annotate=True,
            label_fontsize=5.5 * inner_text_scale,
        )

        add_runtime_change_contours(ax, workload, with_handles=False)
        if "Grok" in workload["name"]:
            ax.text(
                7.5,
                30.0,
                "Compute time\ndominates here",
                ha="center",
                va="center",
                fontsize=5.3 * inner_text_scale,
                color="#2E4B2E",
                bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "#D9E5D9", "alpha": 0.92},
                zorder=10,
            )
        if "vLLM" in workload["name"]:
            ax.text(
                32.0,
                30.0,
                "Memory transfer time\ndominates here",
                ha="center",
                va="center",
                fontsize=5.2 * inner_text_scale,
                color="#2E4B2E",
                bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "#D4DFE8", "alpha": 0.92},
                zorder=10,
            )

    for idx, ax in enumerate(axes):
        if idx > 0:
            ax.set_ylabel("")

    fig.supylabel("Bandwidth [Gbps]", x=0.018, fontsize=7.0 * outer_text_scale)
    fig.supxlabel("Latency [$\\mu$s]", y=0.173, fontsize=7.0 * outer_text_scale)

    handles = [
        mpatches.Patch(facecolor=phase_colors[name], edgecolor="none", label=name)
        for name in PHASE_ORDER
    ]
    band_handles = make_change_band_handles()
    combined_handles = []
    for phase_handle, band_handle in zip(handles, band_handles):
        combined_handles.extend([phase_handle, band_handle])
    combined_labels = [h.get_label() for h in combined_handles]
    fig.legend(
        combined_handles,
        combined_labels,
        ncol=4,
        loc="lower left",
        bbox_to_anchor=(0.03, 0.024, 0.94, 0.11),
        mode="expand",
        framealpha=0.95,
        edgecolor="none",
        fontsize=6.1 * outer_text_scale,
        columnspacing=0.70,
        handletextpad=0.35,
        borderpad=0.32,
        handlelength=1.60,
    )

    for suffix in (".pdf", ".png"):
        out_path = output_dir / f"{stem}{suffix}"
        if suffix == ".png":
            fig.savefig(out_path, dpi=300)
        else:
            fig.savefig(out_path, dpi=240)
    plt.close(fig)


def generate_palette_variants(workloads):
    VARIANT_OUT.mkdir(parents=True, exist_ok=True)

    reference_lines = [
        "Palette variants for fig_2d_sensitivity_workloads",
        "",
    ]
    saved_paths = []
    for variant_name, palette in PALETTE_VARIANTS.items():
        stem = f"fig_2d_sensitivity_workloads_{variant_name}"
        make_workload_comparison_figure(
            workloads,
            output_dir=VARIANT_OUT,
            stem=stem,
            phase_light_colors=palette["light"],
            phase_dark_colors=palette["dark"],
        )
        saved_paths.extend([
            VARIANT_OUT / f"{stem}.pdf",
            VARIANT_OUT / f"{stem}.png",
        ])
        reference_lines.append(f"{variant_name}: {palette['label']}")
        for phase_name in PHASE_ORDER:
            reference_lines.append(
                f"  {phase_name}: light={palette['light'][phase_name]}, dark={palette['dark'][phase_name]}"
            )
        reference_lines.append("")

    (VARIANT_OUT / "palette_reference.txt").write_text("\n".join(reference_lines), encoding="utf-8")
    return saved_paths


def make_frontier_overlay_figure(workloads):
    fig, ax = plt.subplots(figsize=(5.05, 3.3))
    add_common_axes_style(ax)
    ax.set_title("Derived Latency/BW Frontiers Across Workloads", pad=4)

    boundary_handles = []
    for workload in workloads:
        color = WORKLOAD_COLORS[workload["name"]]
        safe_contour(ax, workload["total_change"], NEAR_BASELINE_THRESHOLD, colors=color, linewidths=1.4, linestyles="-", zorder=4)
        boundary_handles.append(Line2D([0], [0], color=color, lw=1.4, label=workload["name"]))

    ax.text(0.88, 0.88, "Latency-dominated", transform=ax.transAxes, ha="right", va="center", fontsize=5.8, color="#444444")
    ax.text(0.12, 0.18, "Bandwidth-dominated", transform=ax.transAxes, ha="left", va="center", fontsize=5.8, color="#444444")
    ax.text(0.62, 0.34, "Both matter", transform=ax.transAxes, ha="center", va="center", fontsize=5.8, color="#444444")
    ax.text(0.14, 0.86, "Near baseline", transform=ax.transAxes, ha="left", va="center", fontsize=5.8, color="#444444")

    ax.legend(boundary_handles, [h.get_label() for h in boundary_handles], loc="lower left", framealpha=0.94, borderpad=0.3, handlelength=2.1)

    for suffix in (".pdf", ".png"):
        out_path = OUT / f"fig_2d_sensitivity_frontiers{suffix}"
        if suffix == ".png":
            fig.savefig(out_path, dpi=300)
        else:
            fig.savefig(out_path)
    plt.close(fig)


def main():
    workloads = [
        prepare_workload("Llama (128 GPUs)", load_llama_curves, DEFAULT_LAT_BASELINE_US, 200.0, "Alps", "cscs", "Alps"),
        prepare_workload("Grok (4096 GPUs)", load_grok_curves, DEFAULT_LAT_BASELINE_US, 800.0, "Azure ND GB200 v6", "azure", "Azure\nND GB200 v6"),
        prepare_workload("vLLM (8 GPUs)", load_vllm_curves, DEFAULT_LAT_BASELINE_US, 200.0, "Alps", "cscs", "Alps"),
    ]
    make_llama_detail_figure(workloads[0])
    make_workload_comparison_figure(workloads)
    make_frontier_overlay_figure(workloads)

    for stem in (
        "fig_2d_sensitivity_llama_detail",
        "fig_2d_sensitivity_workloads",
        "fig_2d_sensitivity_frontiers",
    ):
        print(f"Saved {OUT / f'{stem}.pdf'}")


if __name__ == "__main__":
    main()
