#!/usr/bin/env python3
"""Build a paper-plot versus artifact-result comparison PDF.

The paper PDF is used only while generating the report. It is not copied into
the repository. Each output page shows a cropped paper figure above the
corresponding artifact output.
"""

from __future__ import annotations

import argparse
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
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY. This page redraws committed compact "
        "sensitivity inputs. It does not export or process NSYS files.",
    ),
    Page(
        3,
        "Figure 3: 128 MiB AllReduce",
        8,
        (0.08, 0.055, 0.93, 0.252),
        "pdf",
        "figures/fig3_sensitivity_1x4.pdf",
        None,
        "Artifact output: PLOT-ONLY; raw NSYS validation is separate",
        "PROVENANCE: PLOT-ONLY for the displayed paper-style panel. Separate "
        "validation CSVs were produced by an NSYS -> SQLite -> GOAL -> LP "
        "workflow; building this PDF does not rerun that workflow. Maximum "
        "relative errors: 0.078% and 0.166% for latency; 2.373% and 1.493% "
        "for bandwidth.",
    ),
    Page(
        4,
        "Figure 4: mixed collectives",
        9,
        (0.08, 0.055, 0.485, 0.247),
        "pdf",
        "figures/fig_mixed_16n_ch1.pdf",
        None,
        "Artifact output: PLOT-ONLY; raw NSYS validation is separate",
        "PROVENANCE: PLOT-ONLY for the displayed paper-style panel. Separate "
        "validation CSVs were produced by an NSYS -> SQLite -> GOAL -> LP "
        "workflow; building this PDF does not rerun that workflow. Maximum "
        "relative errors: 0.142% for latency and 0.242% for bandwidth.",
    ),
    Page(
        5,
        "Figure 5: Llama training iteration",
        9,
        (0.565, 0.055, 0.925, 0.247),
        "pdf",
        "figures/fig5_llama7b.pdf",
        None,
        "Artifact output: selected NSYS-derived Composite curve",
        "PROVENANCE: the selected Composite curve was produced by an "
        "NSYS-derived workflow and is committed in the repository. Building "
        "this PDF plots that result without rerunning NSYS. The available raw "
        "entry point, pipeline/reproduce_fig5_from_nsys.sh, regenerates the "
        "Monolithic baseline rather than this committed Composite curve. "
        "Maximum relative error: 0.014853%; mean: 0.004879% over 201 points.",
    ),
    Page(
        6,
        "Figure 6: latency and bandwidth sensitivity",
        10,
        (0.075, 0.047, 0.93, 0.358),
        "pdf",
        "figures/fig_3x3_sensitivity.pdf",
        None,
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY for the displayed panels. The standard full "
        "workflow reruns analysis from committed trace-derived metadata; "
        "building this PDF does not export or process NSYS files.",
    ),
    Page(
        7,
        "Figure 7: monolithic memory footprint",
        10,
        (0.075, 0.49, 0.50, 0.65),
        "pdf",
        "figures/fig6_grok_memory.pdf",
        None,
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY. This page redraws committed compact memory "
        "inputs. It does not export or process NSYS files.",
    ),
    Page(
        8,
        "Figure 8: network-parameter sensitivity",
        11,
        (0.075, 0.05, 0.50, 0.295),
        "pdf",
        "figures/fig8_network_parameters.pdf",
        None,
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY. This page redraws committed compact latency "
        "and bandwidth inputs. It does not export or process NSYS files.",
    ),
    Page(
        9,
        "Figure 9: network cost trajectory",
        11,
        (0.49, 0.30, 0.94, 0.405),
        "pdf",
        "figures/fig9_network_cost.pdf",
        None,
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY. This page redraws committed compact sweep and "
        "cost inputs. It does not export or process NSYS files.",
    ),
    Page(
        10,
        "Figure 10: jitter sensitivity",
        12,
        (0.075, 0.18, 0.50, 0.315),
        "pdf",
        "figures/fig_jitter_3panel.pdf",
        None,
        "Artifact output: PLOT-ONLY from committed inputs",
        "PROVENANCE: PLOT-ONLY. This page redraws committed compact jitter "
        "inputs. It does not export or process NSYS files.",
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


def result_image(page: Page, work: Path, dpi: int) -> Image.Image:
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
