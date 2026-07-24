#!/usr/bin/env python3
"""Run one bounded task from the full SC26 artifact workflow.

The wrapper is used both locally and by the Slurm launcher. Each task writes
large or temporary outputs below ``--scratch`` and records a JSON manifest.
The paper plots and compact comparison inputs remain in the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
# Keep the virtual-environment entry point. Resolving this symlink would bypass
# the environment and launch the system interpreter for child processes.
PYTHON = Path(sys.executable).absolute()


def run(cmd: Sequence[object], timeout: int | None = 2700) -> dict[str, object]:
    printable = [str(item) for item in cmd]
    print(">>>", " ".join(printable), flush=True)
    started = time.perf_counter()
    proc = subprocess.run(
        printable,
        cwd=ROOT,
        env={**os.environ, "MPLBACKEND": os.environ.get("MPLBACKEND", "Agg")},
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    record: dict[str, object] = {
        "cmd": printable,
        "returncode": proc.returncode,
        "elapsed_s": elapsed,
    }
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed with exit code {proc.returncode}: {' '.join(printable)}"
        )
    return record


def compare(
    expected: Path,
    actual: Path,
    output: Path,
    label: str,
    *,
    expected_x: str | None = None,
    actual_x: str | None = None,
    expected_y: str | None = None,
    actual_y: str | None = None,
) -> dict[str, object]:
    cmd: list[object] = [
        PYTHON,
        "scripts/compare_csv.py",
        "--expected",
        expected,
        "--actual",
        actual,
        "--out-dir",
        output,
        "--label",
        label,
        "--points",
        "actual",
    ]
    if expected_x:
        cmd += ["--expected-x-col", expected_x]
    if actual_x:
        cmd += ["--actual-x-col", actual_x]
    if expected_y:
        cmd += ["--expected-y-col", expected_y]
    if actual_y:
        cmd += ["--actual-y-col", actual_y]
    return run(cmd, timeout=600)


def composite_command(
    analysis: Path,
    output: Path,
    cache: Path,
    workers: int,
    extra: Sequence[str],
) -> list[object]:
    return [
        PYTHON,
        "pipeline/run_nccl_composite.py",
        "--analysis-dir",
        analysis,
        "--out",
        output,
        "--cache-dir",
        cache,
        "--clear-cache",
        "--parallel-solve",
        "--max-workers",
        workers,
        *extra,
    ]


def task_core(args: argparse.Namespace) -> list[dict[str, object]]:
    return [
        run(["bash", "reproduce_quick.sh"], timeout=300),
        run([PYTHON, "local_artifact/verify_manifests.py"], timeout=300),
        run([PYTHON, "scripts/check_artifact.py", "--skip-figure"], timeout=300),
        run([PYTHON, "-m", "pytest", "-q"], timeout=900),
    ]


def task_demo(args: argparse.Namespace) -> list[dict[str, object]]:
    return [run([PYTHON, "reproduce_all.py", "--pipeline", "--only", "3"], timeout=900)]


def task_fig3(args: argparse.Namespace) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    specs = [
        (
            "ch1",
            ROOT / "data/output/final_plots/data/ar_128m_16n_ch1",
            ROOT
            / "data/output/final_plots/data/ar_128m_16n_ch1/latency_compressed_runtime.csv",
            [
                "--node-map-mode",
                "rank-block",
                "--ring-duplicate-policy",
                "last",
                "--disable-intra-node-transfer",
            ],
        ),
        (
            "auto",
            ROOT / "data/output/final_plots/data/ar_128m_16n_auto",
            ROOT
            / "data/output/final_plots/data/ar_128m_16n_auto/latency_compressed_runtime.csv",
            [
                "--program-rank",
                "6",
                "--node-map-mode",
                "rank-block",
                "--ring-duplicate-policy",
                "last",
                "--nic-per-rank",
                "--nics-per-node",
                "4",
                "--force-sequential",
            ],
        ),
    ]
    for name, analysis, expected, extra in specs:
        out_dir = args.scratch / "fig3" / name
        actual = out_dir / "composed_runtime.csv"
        records.append(
            run(
                composite_command(
                    analysis,
                    actual,
                    out_dir / "cache",
                    args.workers,
                    extra,
                )
            )
        )
        records.append(
            compare(
                expected,
                actual,
                out_dir / "comparison",
                f"fig3_{name}_composite_vs_paper",
            )
        )
        canonical_dir = ROOT / "results/reproduced/fig3"
        canonical_latency = canonical_dir / f"{name}_latency_monolithic.csv"
        bw_suffix = "_4nic" if name == "auto" else ""
        canonical_bandwidth = canonical_dir / f"{name}_bandwidth_monolithic{bw_suffix}.csv"
        if canonical_latency.is_file():
            records.append(
                compare(
                    analysis / "latency_full_runtime.csv",
                    canonical_latency,
                    out_dir / "canonical_latency_comparison",
                    f"fig3_{name}_best_raw_vs_paper",
                )
            )
        if canonical_bandwidth.is_file():
            records.append(
                compare(
                    analysis / "bw_composite_runtime.csv",
                    canonical_bandwidth,
                    out_dir / "canonical_bandwidth_comparison",
                    f"fig3_{name}_best_raw_bandwidth_vs_paper",
                    expected_x="G",
                    actual_x="G",
                    expected_y="runtime",
                    actual_y="runtime",
                )
            )
    return records


def task_fig4(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig4"
    actual = out_dir / "composed_runtime.csv"
    analysis = ROOT / "data/output/final_plots/data/mixed_16n_ch1"
    expected = analysis / "latency_full_runtime.csv"
    records = [
        run(
            composite_command(
                analysis,
                actual,
                out_dir / "cache",
                args.workers,
                [
                    "--node-map-mode",
                    "rank-block",
                    "--ring-duplicate-policy",
                    "last",
                    "--nic-per-rank",
                    "--force-sequential",
                ],
            )
        )
    ]
    records.append(
        compare(expected, actual, out_dir / "comparison", "fig4_composite_vs_paper")
    )
    records.append(
        compare(
            expected,
            ROOT / "local_artifact/results/fig4/latency_monolithic_barriers.csv",
            out_dir / "canonical_latency_comparison",
            "fig4_best_raw_latency_vs_paper",
        )
    )
    records.append(
        compare(
            analysis / "bw_composite_runtime.csv",
            ROOT / "local_artifact/results/fig4/bandwidth_monolithic_barriers.csv",
            out_dir / "canonical_bandwidth_comparison",
            "fig4_best_raw_bandwidth_vs_paper",
            expected_x="G",
            actual_x="G",
            expected_y="runtime",
            actual_y="runtime",
        )
    )
    return records


def task_fig5(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig5"
    expected = ROOT / "data/output/llama7b/comp_100pct/sweeps/composed_runtime.csv"
    actual = ROOT / "local_artifact/results/fig5/composed_runtime.csv"
    return [
        compare(
            expected,
            actual,
            out_dir / "comparison",
            "fig5_best_recovered_composite_vs_paper",
        )
    ]


def task_fig6_latency(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig6_latency"
    actual = out_dir / "composed_runtime.csv"
    analysis = ROOT / "data/workspaces/llama7b_n32_spcl_20260407/analysis"
    expected = (
        ROOT
        / "data/workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/composed_runtime.csv"
    )
    records = [
        run(
            composite_command(
                analysis,
                actual,
                out_dir / "cache",
                args.workers,
                [
                    "--node-map-mode",
                    "rank-block",
                    "--force-sequential",
                    "--nic-per-rank",
                    "--nics-per-node",
                    "4",
                ],
            )
        )
    ]
    records.append(
        compare(
            expected,
            actual,
            out_dir / "comparison",
            "fig6_llama_latency_vs_paper",
        )
    )
    return records


def task_fig6_bandwidth(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig6_bandwidth"
    actual = out_dir / "bandwidth_sensitivity.csv"
    analysis = ROOT / "data/workspaces/llama7b_n32_spcl_20260407/analysis"
    expected = (
        ROOT
        / "data/workspaces/llama7b_n32_spcl_20260407/output/"
        "bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv"
    )
    records = [
        run(
            [
                PYTHON,
                "pipeline/run_nccl_bw_sensitivity.py",
                "--analysis-dir",
                analysis,
                "--out",
                actual,
                "--cache-dir",
                out_dir / "cache",
                "--clear-cache",
                "--fixed-l-ns",
                "4000",
                "--min-bw-gbps",
                "10",
                "--max-bw-gbps",
                "1600",
                "--num-points",
                "20",
                "--spacing",
                "log",
                "--max-workers",
                args.workers,
                "--node-map-mode",
                "rank-block",
                "--force-sequential",
                "--nic-per-rank",
                "--nics-per-node",
                "4",
            ]
        )
    ]
    records.append(
        compare(
            expected,
            actual,
            out_dir / "comparison",
            "fig6_llama_bandwidth_vs_paper",
            expected_x="bw_gbps",
            actual_x="bw_gbps",
            expected_y="runtime_ns",
            actual_y="runtime_ns",
        )
    )
    return records


def require_grok_analysis(args: argparse.Namespace) -> Path:
    if args.grok_analysis_dir is None:
        raise SystemExit(
            "Grok 4096-GPU regeneration requires --grok-analysis-dir pointing "
            "to N1024 metadata. It is never inferred or downloaded."
        )
    analysis = args.grok_analysis_dir.resolve()
    for name in ("collective_instances.csv", "comm_ring_info.csv"):
        if not (analysis / name).is_file():
            raise SystemExit(f"missing Grok input: {analysis / name}")
    return analysis


def task_grok4096_latency(args: argparse.Namespace) -> list[dict[str, object]]:
    analysis = require_grok_analysis(args)
    out_dir = args.scratch / "grok4096_latency"
    actual = out_dir / "composed_runtime.csv"
    expected = ROOT / "data/output/grok_final/grok_N1024_latency_sweep.csv"
    records = [
        run(
            composite_command(
                analysis,
                actual,
                out_dir / "cache",
                args.workers,
                [],
            ),
            timeout=None,
        )
    ]
    records.append(
        compare(
            expected,
            actual,
            out_dir / "comparison",
            "grok4096_latency_vs_paper",
        )
    )
    return records


def task_grok4096_bandwidth(args: argparse.Namespace) -> list[dict[str, object]]:
    analysis = require_grok_analysis(args)
    out_dir = args.scratch / "grok4096_bandwidth"
    actual = out_dir / "bandwidth_sensitivity.csv"
    expected = ROOT / "data/output/grok_final/grok_N1024_bw_sweep.csv"
    records = [
        run(
            [
                PYTHON,
                "pipeline/run_nccl_bw_sensitivity.py",
                "--analysis-dir",
                analysis,
                "--out",
                actual,
                "--cache-dir",
                out_dir / "cache",
                "--clear-cache",
                "--fixed-l-ns",
                "4000",
                "--min-bw-gbps",
                "10",
                "--max-bw-gbps",
                "1600",
                "--num-points",
                "20",
                "--spacing",
                "log",
                "--max-workers",
                args.workers,
            ],
            timeout=None,
        )
    ]
    records.append(
        compare(
            expected,
            actual,
            out_dir / "comparison",
            "grok4096_bandwidth_vs_paper",
            expected_x="bw_gbps",
            actual_x="bw_gbps",
            expected_y="runtime_ns",
            actual_y="runtime_ns",
        )
    )
    return records


TASKS = {
    "core": task_core,
    "demo": task_demo,
    "fig3": task_fig3,
    "fig4": task_fig4,
    "fig5": task_fig5,
    "fig6-latency": task_fig6_latency,
    "fig6-bandwidth": task_fig6_bandwidth,
    "grok4096-latency": task_grok4096_latency,
    "grok4096-bandwidth": task_grok4096_bandwidth,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=sorted(TASKS))
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--grok-analysis-dir", type=Path)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    args.scratch = args.scratch.resolve()
    args.scratch.mkdir(parents=True, exist_ok=True)

    started = time.time()
    status = "ok"
    commands: list[dict[str, object]] = []
    try:
        commands = TASKS[args.task](args)
    except BaseException as exc:
        status = "failed"
        failure = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest = {
            "task": args.task,
            "status": status,
            "started_unix": started,
            "ended_unix": time.time(),
            "python": str(PYTHON),
            "repo": str(ROOT),
            "scratch": str(args.scratch),
            "commands": commands,
        }
        if status != "ok":
            manifest["failure"] = failure
        task_dir = args.scratch / "manifests"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / f"{args.task}.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
