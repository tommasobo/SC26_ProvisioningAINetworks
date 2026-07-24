#!/usr/bin/env python3
"""Build a paper-plot versus artifact-result comparison PDF.

The paper PDF is used only while generating the report. It is not copied into
the repository. Each output page shows a cropped paper figure above the
corresponding artifact output or raw-derived comparison.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Page:
    number: int
    title: str
    paper_page: int
    paper_crop: tuple[float, float, float, float]
    result_kind: str
    result_path: str | None
    result_crop: tuple[float, float, float, float] | None
    result_label: str
    note: str


PAGES = (
    Page(
        1,
        "Figure 1: workload sensitivity maps",
        3,
        (0.50, 0.215, 0.94, 0.380),
        "pdf",
        "figures/fig_2d_sensitivity_workloads.pdf",
        None,
        "Artifact output: compact-data redraw",
        "Exact numerical redraw from existing one-dimensional sweeps. "
        "No upstream experiment was rerun.",
    ),
    Page(
        3,
        "Figure 3: 128 MiB AllReduce",
        8,
        (0.08, 0.055, 0.93, 0.252),
        "fig3",
        None,
        None,
        "Raw-derived result: selected final Alps curves",
        "Maximum relative errors: 0.078% and 0.166% for latency; "
        "2.373% and 1.493% for bandwidth.",
    ),
    Page(
        4,
        "Figure 4: mixed collectives",
        9,
        (0.08, 0.055, 0.485, 0.247),
        "fig4",
        None,
        None,
        "Raw-derived result: selected job 1808340 campaign",
        "Maximum relative errors: 0.142% for latency and 0.242% for "
        "bandwidth. The matching campaign conflicts with the message-size "
        "range stated in the paper.",
    ),
    Page(
        5,
        "Figure 5: Llama training iteration",
        9,
        (0.565, 0.055, 0.925, 0.247),
        "fig5",
        None,
        None,
        "Closest recovered raw-derived Composite curve",
        "Maximum relative error 0.014853%; mean relative error 0.004879% "
        "over 201 points. The exact paper-era per-motif transformation is "
        "not available.",
    ),
    Page(
        6,
        "Figure 6: latency and bandwidth sensitivity",
        10,
        (0.075, 0.047, 0.93, 0.358),
        "pdf",
        "local_artifact/figures/figure6_reproduced.pdf",
        None,
        "Reproduction evidence: Llama and vLLM panels",
        "Llama uses the strongest retained metadata rerun. The archived vLLM "
        "job point replays exactly, but the full curve differs. Grok 4k uses "
        "existing CSV data and was not rerun.",
    ),
    Page(
        7,
        "Figure 7: monolithic memory footprint",
        10,
        (0.075, 0.49, 0.50, 0.65),
        "pdf",
        "figures/fig6_grok_memory.pdf",
        None,
        "Artifact output: compact-data redraw",
        "Exact numerical redraw of the retained memory data. "
        "No large-memory LP experiment was rerun.",
    ),
    Page(
        8,
        "Figure 8: network-parameter sensitivity",
        11,
        (0.075, 0.05, 0.50, 0.295),
        "pdf",
        "figures/fig_network_perf_combined.pdf",
        (0.00, 0.00, 1.00, 0.49),
        "Artifact output: published-value redraw",
        "The published latency and bandwidth values are embedded in the "
        "plotting script. No upstream experiment was rerun.",
    ),
    Page(
        9,
        "Figure 9: network cost trajectory",
        11,
        (0.49, 0.30, 0.94, 0.405),
        "pdf",
        "figures/fig_network_perf_combined.pdf",
        (0.00, 0.49, 1.00, 1.00),
        "Artifact output: published-value redraw",
        "The published cost and performance values are embedded in the "
        "plotting script. No upstream pricing experiment was rerun.",
    ),
    Page(
        10,
        "Figure 10: jitter sensitivity",
        12,
        (0.075, 0.18, 0.50, 0.315),
        "pdf",
        "figures/fig_jitter_3panel.pdf",
        None,
        "Artifact output: compact-data redraw",
        "Exact numerical redraw from the retained jitter data. "
        "No stochastic jitter experiment was rerun.",
    ),
)


def run_ghostscript(source: Path, target_pattern: Path, dpi: int) -> None:
    gs = shutil.which("gs")
    if gs is None:
        raise RuntimeError("Ghostscript executable 'gs' is required")
    subprocess.run(
        [
            gs,
            "-q",
            "-dSAFER",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=png16m",
            f"-r{dpi}",
            f"-sOutputFile={target_pattern}",
            str(source),
        ],
        check=True,
    )


def crop_fraction(
    image: Image.Image,
    crop: tuple[float, float, float, float] | None,
) -> Image.Image:
    if crop is None:
        return image.copy()
    left, top, right, bottom = crop
    return image.crop(
        (
            round(left * image.width),
            round(top * image.height),
            round(right * image.width),
            round(bottom * image.height),
        )
    )


def trim_white(image: Image.Image, pad: int = 8) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    nonwhite = np.any(rgb < 248, axis=2)
    if not np.any(nonwhite):
        return image.copy()
    ys, xs = np.where(nonwhite)
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(image.width, int(xs.max()) + pad + 1)
    bottom = min(image.height, int(ys.max()) + pad + 1)
    return image.crop((left, top, right, bottom))


def render_pdf(pdf: Path, work: Path, stem: str, dpi: int) -> Image.Image:
    target = work / f"{stem}_%02d.png"
    run_ghostscript(pdf, target, dpi)
    first_page = work / f"{stem}_01.png"
    if not first_page.is_file():
        raise RuntimeError(f"Ghostscript did not render {pdf}")
    return trim_white(Image.open(first_page).convert("RGB"))


def figure_to_image(fig: plt.Figure, dpi: int = 190) -> Image.Image:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buffer.seek(0)
    return trim_white(Image.open(buffer).convert("RGB"))


def read_xy(path: Path, x_col: str, y_col: str) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_csv(path)
    values = frame[[x_col, y_col]].apply(pd.to_numeric, errors="coerce").dropna()
    return values[x_col].to_numpy(float), values[y_col].to_numpy(float)


def read_bandwidth(path: Path) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_csv(path)
    runtime_col = "runtime_ns" if "runtime_ns" in frame else "runtime"
    runtime = pd.to_numeric(frame[runtime_col], errors="coerce").to_numpy(float)
    if "bw_gbps" in frame:
        bandwidth = pd.to_numeric(frame["bw_gbps"], errors="coerce").to_numpy(float)
    else:
        gap = pd.to_numeric(frame["G"], errors="coerce").to_numpy(float)
        bandwidth = np.divide(
            8.0,
            gap,
            out=np.full_like(gap, np.nan),
            where=gap > 0,
        )
    valid = np.isfinite(bandwidth) & np.isfinite(runtime)
    order = np.argsort(bandwidth[valid])
    return bandwidth[valid][order], runtime[valid][order]


def style_axis(ax: plt.Axes, title: str, xlabel: str) -> None:
    ax.set_title(title, fontsize=10, pad=5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Runtime [ms]")
    ax.grid(True, linestyle=":", alpha=0.35)


def plot_pair(
    ax: plt.Axes,
    paper_x: np.ndarray,
    paper_y: np.ndarray,
    result_x: np.ndarray,
    result_y: np.ndarray,
    title: str,
    xlabel: str,
) -> None:
    ax.plot(paper_x, paper_y / 1e6, "--", color="#666666", label="Paper CSV")
    ax.plot(result_x, result_y / 1e6, color="#d33f2f", label="Reproduced")
    style_axis(ax, title, xlabel)


def make_fig3_result() -> Image.Image:
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 5.2), constrained_layout=True)
    specs = (
        (
            axes[0, 0],
            "data/output/final_plots/data/ar_128m_16n_ch1/latency_compressed_runtime.csv",
            "results/reproduced/fig3/ch1_latency_monolithic.csv",
            "Latency, 1 channel (max 0.078%)",
            "latency",
        ),
        (
            axes[0, 1],
            "data/output/final_plots/data/ar_128m_16n_auto/latency_compressed_runtime.csv",
            "results/reproduced/fig3/auto_latency_monolithic.csv",
            "Latency, automatic channels (max 0.166%)",
            "latency",
        ),
        (
            axes[1, 0],
            "data/output/final_plots/data/ar_128m_16n_ch1/bw_composite_runtime.csv",
            "results/reproduced/fig3/ch1_bandwidth_monolithic.csv",
            "Bandwidth, 1 channel (max 2.373%)",
            "bandwidth",
        ),
        (
            axes[1, 1],
            "data/output/final_plots/data/ar_128m_16n_auto/bw_composite_runtime.csv",
            "results/reproduced/fig3/auto_bandwidth_monolithic_4nic.csv",
            "Bandwidth, automatic channels (max 1.493%)",
            "bandwidth",
        ),
    )
    for ax, paper_path, result_path, title, kind in specs:
        if kind == "latency":
            px, py = read_xy(ROOT / paper_path, "L", "runtime")
            rx, ry = read_xy(ROOT / result_path, "L", "runtime")
            plot_pair(ax, px / 1e3, py, rx / 1e3, ry, title, "L [µs]")
        else:
            px, py = read_bandwidth(ROOT / paper_path)
            rx, ry = read_bandwidth(ROOT / result_path)
            plot_pair(ax, px, py, rx, ry, title, "Bandwidth [Gbps]")
            ax.set_xlim(60, 1600)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    return figure_to_image(fig)


def make_fig4_result() -> Image.Image:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)
    px, py = read_xy(
        ROOT / "data/output/final_plots/data/mixed_16n_ch1/latency_full_runtime.csv",
        "L",
        "runtime",
    )
    rx, ry = read_xy(
        ROOT / "local_artifact/results/fig4/latency_monolithic_barriers.csv",
        "L",
        "runtime",
    )
    plot_pair(
        axes[0],
        px / 1e3,
        py,
        rx / 1e3,
        ry,
        "Latency sweep (max 0.142%)",
        "L [µs]",
    )
    px, py = read_bandwidth(
        ROOT / "data/output/final_plots/data/mixed_16n_ch1/bw_composite_runtime.csv"
    )
    rx, ry = read_bandwidth(
        ROOT / "local_artifact/results/fig4/bandwidth_monolithic_barriers.csv"
    )
    plot_pair(
        axes[1],
        px,
        py,
        rx,
        ry,
        "Independent bandwidth check (max 0.242%)",
        "Bandwidth [Gbps]",
    )
    axes[1].set_xlim(60, 1600)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    return figure_to_image(fig)


def make_fig5_result() -> Image.Image:
    paper_x, paper_y = read_xy(
        ROOT / "data/output/llama7b/comp_100pct/sweeps/composed_runtime.csv",
        "L",
        "runtime",
    )
    result_x, result_y = read_xy(
        ROOT / "local_artifact/results/fig5/composed_runtime.csv",
        "L",
        "runtime",
    )
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)
    plot_pair(
        axes[0],
        paper_x / 1e3,
        paper_y,
        result_x / 1e3,
        result_y,
        "Composite runtime overlay",
        "L [µs]",
    )
    reference = np.interp(result_x, paper_x, paper_y)
    difference = 100.0 * (result_y - reference) / reference
    axes[1].plot(result_x / 1e3, difference, color="#d33f2f")
    axes[1].axhline(0.0, color="#666666", linestyle="--", linewidth=1)
    axes[1].set_title("Pointwise relative difference", fontsize=10, pad=5)
    axes[1].set_xlabel("L [µs]")
    axes[1].set_ylabel("Difference [%]")
    axes[1].grid(True, linestyle=":", alpha=0.35)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    return figure_to_image(fig)


def result_image(page: Page, work: Path, dpi: int) -> Image.Image:
    if page.result_kind == "fig3":
        return make_fig3_result()
    if page.result_kind == "fig4":
        return make_fig4_result()
    if page.result_kind == "fig5":
        return make_fig5_result()
    if page.result_kind != "pdf" or page.result_path is None:
        raise RuntimeError(f"Unsupported result type for Figure {page.number}")
    image = render_pdf(ROOT / page.result_path, work, f"result_{page.number}", dpi)
    return trim_white(crop_fraction(image, page.result_crop))


def add_image(ax: plt.Axes, image: Image.Image, label: str) -> None:
    ax.imshow(image)
    ax.axis("off")
    ax.set_title(label, loc="left", fontsize=10, fontweight="bold", pad=5)


def build_report(paper: Path, output: Path, dpi: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sc26-figure-compare-") as temporary:
        work = Path(temporary)
        run_ghostscript(paper, work / "paper_%02d.png", dpi)
        rendered_paper = {
            number: Image.open(work / f"paper_{number:02d}.png").convert("RGB")
            for number in {page.paper_page for page in PAGES}
        }

        with PdfPages(output) as pdf:
            for page in PAGES:
                paper_image = trim_white(
                    crop_fraction(rendered_paper[page.paper_page], page.paper_crop)
                )
                reproduced_image = result_image(page, work, dpi)

                fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
                fig.suptitle(page.title, fontsize=16, fontweight="bold", y=0.975)
                paper_ax = fig.add_axes([0.045, 0.535, 0.91, 0.365])
                result_ax = fig.add_axes([0.045, 0.105, 0.91, 0.355])
                add_image(paper_ax, paper_image, "Paper plot")
                add_image(result_ax, reproduced_image, page.result_label)
                fig.text(
                    0.045,
                    0.025,
                    textwrap.fill(page.note, width=145),
                    ha="left",
                    va="bottom",
                    fontsize=8.5,
                    color="#333333",
                )
                fig.text(
                    0.955,
                    0.025,
                    f"{page.number}",
                    ha="right",
                    va="bottom",
                    fontsize=8,
                    color="#666666",
                )
                pdf.savefig(fig)
                plt.close(fig)

            metadata = pdf.infodict()
            metadata["Title"] = "SC26 paper plots versus artifact results"
            metadata["Author"] = "Provisioning Networks artifact"
            metadata["Subject"] = "Figures 1 and 3 to 10"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, required=True, help="Current paper PDF")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/comparison/SC26_paper_vs_artifact.pdf",
    )
    parser.add_argument("--dpi", type=int, default=240)
    args = parser.parse_args()
    if not args.paper.is_file():
        parser.error(f"paper PDF not found: {args.paper}")
    build_report(args.paper.resolve(), args.output.resolve(), args.dpi)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
