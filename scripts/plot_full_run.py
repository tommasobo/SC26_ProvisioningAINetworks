#!/usr/bin/env python3
"""Render paper-style figures from the outputs of a completed full run.

The numerical tasks write their results below a scratch directory. This
script stages the repository's compact plotting inputs in the same scratch
directory, substitutes the freshly generated Figure 3--6 results, and runs
the normal plotting scripts without modifying repository data or figures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FRESH_INPUTS = {
    "fig3_ch1_latency": Path("fig3/ch1/composed_runtime.csv"),
    "fig3_ch1_bandwidth": Path("fig3/ch1/bandwidth_sensitivity.csv"),
    "fig3_auto_latency": Path("fig3/auto/composed_runtime.csv"),
    "fig3_auto_bandwidth": Path("fig3/auto/bandwidth_sensitivity.csv"),
    "fig4_latency": Path("fig4/composed_runtime.csv"),
    "fig5_composite": Path("fig5/out/composed_runtime.csv"),
    "fig6_llama_latency": Path("fig6_latency/composed_runtime.csv"),
    "fig6_llama_bandwidth": Path("fig6_bandwidth/bandwidth_sensitivity.csv"),
}

PLOT_SCRIPTS = {
    "3": "scripts/fig03_allreduce_1x4.py",
    "4": "scripts/fig04_mixed_collectives.py",
    "5": "scripts/fig05_llama_iteration.py",
    "6": "scripts/fig06_sensitivity_grid.py",
}

SUPPLIED_PLOT_SCRIPTS = (
    "scripts/fig01_sensitivity_maps.py",
    "scripts/fig07_memory_scaling.py",
    "scripts/fig08_09_cluster_params_cost.py",
    "scripts/fig10_jitter.py",
)

GENERATED_OUTPUTS = {
    "3": (
        "fig3_sensitivity_1x4.pdf",
        "fig3_sensitivity_1x4.png",
        "fig3_sensitivity_2x2.pdf",
        "fig3_sensitivity_2x2.png",
    ),
    "4": ("fig_mixed_16n_ch1.pdf", "fig_mixed_16n_ch1.png"),
    "5": ("fig5_llama7b.pdf", "fig5_llama7b.png"),
    "6": ("fig_3x3_sensitivity.pdf", "fig_3x3_sensitivity.png"),
}

SUPPLIED_OUTPUTS = {
    "1": ("fig_2d_sensitivity_workloads.pdf", "fig_2d_sensitivity_workloads.png"),
    "7": ("fig6_grok_memory.pdf", "fig6_grok_memory.png"),
    "8": ("fig8_network_parameters.pdf", "fig8_network_parameters.png"),
    "9": ("fig9_network_cost.pdf", "fig9_network_cost.png"),
    "10": ("fig_jitter_3panel.pdf", "fig_jitter_3panel.png"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_fresh_inputs(scratch: Path) -> dict[str, Path]:
    resolved = {name: scratch / relative for name, relative in FRESH_INPUTS.items()}
    missing = [path for path in resolved.values() if not path.is_file()]
    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise SystemExit(
            "Full-run plotting requires fresh numerical outputs. Missing:\n"
            f"{formatted}"
        )
    return resolved


def require_columns(path: Path, alternatives: tuple[set[str], ...]) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            columns = set(next(reader))
        except StopIteration as exc:
            raise SystemExit(f"Fresh result is empty: {path}") from exc
    if not any(required <= columns for required in alternatives):
        expected = " or ".join(", ".join(sorted(item)) for item in alternatives)
        raise SystemExit(
            f"Fresh result has incompatible columns: {path}\n"
            f"  expected {expected}; found {', '.join(sorted(columns))}"
        )
    return columns


def copy_result(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def stage_fig3_bandwidth(source: Path, target: Path) -> None:
    """Convert a fresh bandwidth sweep to the G,runtime plot input schema."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open(newline="", encoding="utf-8") as src:
        reader = csv.DictReader(src)
        fields = set(reader.fieldnames or ())
        rows = list(reader)

    if {"G", "runtime"} <= fields:
        output = [{"G": row["G"], "runtime": row["runtime"]} for row in rows]
    elif {"G_inter_ns_per_byte", "runtime_ns"} <= fields:
        output = [
            {
                "G": row["G_inter_ns_per_byte"],
                "runtime": row["runtime_ns"],
            }
            for row in rows
        ]
    elif {"bw_gbps", "runtime_ns"} <= fields:
        output = []
        for row in rows:
            bandwidth = float(row["bw_gbps"])
            if bandwidth <= 0:
                continue
            output.append(
                {
                    "G": f"{8.0 / bandwidth:.17g}",
                    "runtime": row["runtime_ns"],
                }
            )
    else:
        raise SystemExit(
            f"Fresh Figure 3 bandwidth result has incompatible columns: {source}"
        )

    if not output:
        raise SystemExit(f"Fresh Figure 3 bandwidth result has no data rows: {source}")
    with target.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=["G", "runtime"])
        writer.writeheader()
        writer.writerows(output)


def run_plot(script: str, environment: dict[str, str]) -> None:
    command = [sys.executable, str(ROOT / script)]
    print(">>>", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def output_records(figure_dir: Path, names: tuple[str, ...]) -> list[dict[str, object]]:
    records = []
    for name in names:
        path = figure_dir / name
        if not path.is_file():
            raise SystemExit(f"Plot script did not produce expected output: {path}")
        records.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return records


def fresh_records(
    sources: dict[str, Path],
    names: tuple[str, ...],
) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "path": str(sources[name]),
            "bytes": sources[name].stat().st_size,
            "sha256": sha256(sources[name]),
        }
        for name in names
    ]


def task_input_stage(scratch: Path, task: str) -> str:
    path = scratch / "manifests" / f"{task}.json"
    if not path.is_file():
        return "fresh analysis output"
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("input_stage", "fresh analysis output"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scratch",
        required=True,
        type=Path,
        help="Scratch directory populated by reproduce_full.sh tasks",
    )
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)

    sources = require_fresh_inputs(scratch)
    for name in (
        "fig3_ch1_latency",
        "fig3_auto_latency",
        "fig4_latency",
        "fig5_composite",
        "fig6_llama_latency",
    ):
        require_columns(sources[name], ({"L", "runtime"},))
    for name in ("fig3_ch1_bandwidth", "fig3_auto_bandwidth"):
        require_columns(
            sources[name],
            (
                {"G", "runtime"},
                {"G_inter_ns_per_byte", "runtime_ns"},
                {"bw_gbps", "runtime_ns"},
            ),
        )
    require_columns(
        sources["fig6_llama_bandwidth"],
        ({"bw_gbps", "runtime_ms"},),
    )

    plot_inputs = scratch / "plot_inputs"
    staged_data = plot_inputs / "data"
    fig5_results = plot_inputs / "fig5_results"
    figure_dir = scratch / "figures"
    shutil.copytree(ROOT / "data", staged_data, dirs_exist_ok=True)
    fig5_results.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    fig3_destinations = {
        "fig3_ch1_latency": (
            staged_data
            / "output/final_plots/data/ar_128m_16n_ch1/"
            "latency_composite_runtime.csv"
        ),
        "fig3_auto_latency": (
            staged_data
            / "output/final_plots/data/ar_128m_16n_auto/"
            "latency_composite_runtime.csv"
        ),
    }
    for name, destination in fig3_destinations.items():
        copy_result(sources[name], destination)
    stage_fig3_bandwidth(
        sources["fig3_ch1_bandwidth"],
        staged_data / "output/final_plots/data/ar_128m_16n_ch1/bw_composite_runtime.csv",
    )
    stage_fig3_bandwidth(
        sources["fig3_auto_bandwidth"],
        staged_data / "output/final_plots/data/ar_128m_16n_auto/bw_composite_runtime.csv",
    )

    optional_fresh: dict[str, Path] = {}
    for name, experiment in (("ch1", "ar_128m_16n_ch1"), ("auto", "ar_128m_16n_auto")):
        monolithic = scratch / "fig3" / name / "monolithic_runtime.csv"
        monolithic_bw = scratch / "fig3" / name / "monolithic_bandwidth.csv"
        experiment_dir = staged_data / "output/final_plots/data" / experiment
        if monolithic.is_file():
            copy_result(monolithic, experiment_dir / "latency_full_runtime.csv")
            optional_fresh[f"fig3_{name}_monolithic_latency"] = monolithic
        else:
            (experiment_dir / "latency_full_runtime.csv").unlink(missing_ok=True)
        if monolithic_bw.is_file():
            stage_fig3_bandwidth(
                monolithic_bw,
                experiment_dir / "bw_monolithic_runtime.csv",
            )
            optional_fresh[f"fig3_{name}_monolithic_bandwidth"] = monolithic_bw

    copy_result(
        sources["fig4_latency"],
        staged_data
        / "output/final_plots/data/mixed_16n_ch1/latency_composite_runtime.csv",
    )
    fig4_dir = staged_data / "output/final_plots/data/mixed_16n_ch1"
    fig4_monolithic = scratch / "fig4/monolithic_runtime.csv"
    if fig4_monolithic.is_file():
        copy_result(fig4_monolithic, fig4_dir / "latency_full_runtime.csv")
        optional_fresh["fig4_monolithic_latency"] = fig4_monolithic
    else:
        (fig4_dir / "latency_full_runtime.csv").unlink(missing_ok=True)
    copy_result(sources["fig5_composite"], fig5_results / "composed_runtime.csv")
    copy_result(
        sources["fig6_llama_latency"],
        staged_data
        / "workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/"
        "composed_runtime.csv",
    )
    copy_result(
        sources["fig6_llama_bandwidth"],
        staged_data
        / "workspaces/llama7b_n32_spcl_20260407/output/"
        "bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "MPLBACKEND": "Agg",
            "SC26_DATA_ROOT": str(staged_data),
            "SC26_FIGURE_DIR": str(figure_dir),
            "SC26_FIG5_RESULT_DIR": str(fig5_results),
            "SC26_FULL_RUN": "1",
        }
    )
    for script in PLOT_SCRIPTS.values():
        run_plot(script, environment)
    supplied_environment = {
        **environment,
        "SC26_DATA_ROOT": str(ROOT / "data"),
    }
    for script in SUPPLIED_PLOT_SCRIPTS:
        run_plot(script, supplied_environment)

    figures: dict[str, dict[str, object]] = {
        "3": {
            "input_stage": "fresh_analysis_with_supplied_plot_context",
            "analysis_origin": task_input_stage(scratch, "fig3"),
            "fresh_inputs": fresh_records(
                sources,
                (
                    "fig3_ch1_latency",
                    "fig3_ch1_bandwidth",
                    "fig3_auto_latency",
                    "fig3_auto_bandwidth",
                ),
            ),
            "additional_fresh_inputs": fresh_records(
                optional_fresh,
                tuple(name for name in optional_fresh if name.startswith("fig3_")),
            ),
            "supplied_context": ["Stock LLAMP, LGS, and measured hardware inputs"],
            "outputs": output_records(figure_dir, GENERATED_OUTPUTS["3"]),
        },
        "4": {
            "input_stage": "fresh_analysis_with_supplied_plot_context",
            "analysis_origin": task_input_stage(scratch, "fig4"),
            "fresh_inputs": fresh_records(sources, ("fig4_latency",)),
            "additional_fresh_inputs": fresh_records(
                optional_fresh,
                tuple(name for name in optional_fresh if name.startswith("fig4_")),
            ),
            "supplied_context": ["LGS and measured hardware inputs"],
            "outputs": output_records(figure_dir, GENERATED_OUTPUTS["4"]),
        },
        "5": {
            "input_stage": "fresh_analysis_with_supplied_plot_context",
            "analysis_origin": task_input_stage(scratch, "fig5"),
            "fresh_inputs": fresh_records(sources, ("fig5_composite",)),
            "supplied_context": ["Monolithic LP, LGS, and measured hardware inputs"],
            "outputs": output_records(figure_dir, GENERATED_OUTPUTS["5"]),
        },
        "6": {
            "input_stage": "fresh_llama_analysis_with_supplied_grok_vllm_context",
            "analysis_origin": {
                "latency": task_input_stage(scratch, "fig6-latency"),
                "bandwidth": task_input_stage(scratch, "fig6-bandwidth"),
            },
            "fresh_inputs": fresh_records(
                sources,
                ("fig6_llama_latency", "fig6_llama_bandwidth"),
            ),
            "supplied_context": [
                "Grok 4,096-GPU and vLLM panels",
                "LGS and measured hardware inputs",
            ],
            "outputs": output_records(figure_dir, GENERATED_OUTPUTS["6"]),
        },
    }

    for figure, names in SUPPLIED_OUTPUTS.items():
        figures[figure] = {
            "input_stage": "plot_from_supplied_numerical_data",
            "outputs": output_records(figure_dir, names),
        }

    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scratch": str(scratch),
        "plot_inputs": str(plot_inputs),
        "figure_dir": str(figure_dir),
        "figures": figures,
    }
    manifest_path = scratch / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
