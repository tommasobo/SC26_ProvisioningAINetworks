#!/usr/bin/env python3
"""Run one task from the full SC26 artifact workflow.

The wrapper is used both locally and by the Slurm launcher. Each task writes
large or temporary outputs below ``--scratch`` and records a JSON manifest.
The final plotting task reads the newly generated CSV files from scratch and
passes them to the paper-style plotting scripts.
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


def bandwidth_command(
    analysis: Path,
    output: Path,
    cache: Path,
    workers: int,
    extra: Sequence[str],
    *,
    fixed_l_ns: int = 5000,
) -> list[object]:
    # Match the paper sweep at G=0.002,...,0.120 ns/byte. The plotting
    # scripts display bandwidth, so pass the equivalent Gbit/s values.
    bandwidths = [8.0 / (index * 0.002) for index in range(1, 61)]
    return [
        PYTHON,
        "pipeline/run_nccl_bw_sensitivity.py",
        "--analysis-dir",
        analysis,
        "--out",
        output,
        "--cache-dir",
        cache,
        "--clear-cache",
        "--fixed-l-ns",
        fixed_l_ns,
        "--bandwidths",
        *[f"{value:.12g}" for value in bandwidths],
        "--max-workers",
        workers,
        *extra,
    ]


def analysis_input(
    args: argparse.Namespace,
    records: list[dict[str, object]],
    *,
    trace_subdir: str,
    packaged: Path,
    nics_per_node: int = 4,
) -> Path:
    """Use supplied metadata or regenerate it from an explicit NSYS tree."""
    if args.trace_root is None:
        return packaged

    nsys_dir = args.trace_root / trace_subdir
    if not nsys_dir.is_dir():
        raise FileNotFoundError(f"raw trace directory not found: {nsys_dir}")
    raw_work = args.scratch / "raw" / trace_subdir
    sqlite_dir = raw_work / "sqlite"
    analysis_dir = raw_work / "analysis"
    records.append(
        run(
            [
                PYTHON,
                "pipeline/export_nsys.py",
                "--input-dir",
                nsys_dir,
                "--output-dir",
                sqlite_dir,
                "--workers",
                args.workers,
            ],
            timeout=3600,
        )
    )
    records.append(
        run(
            [
                PYTHON,
                "pipeline/run_nccl_generator.py",
                "--sqlite-dir",
                sqlite_dir,
                "--out-dir",
                analysis_dir,
                "--nics-per-node",
                nics_per_node,
            ],
            timeout=3600,
        )
    )
    return analysis_dir


def raw_monolithic_outputs(
    args: argparse.Namespace,
    records: list[dict[str, object]],
    *,
    analysis: Path,
    out_dir: Path,
    add_barriers: bool = False,
    nic_per_rank: bool = False,
) -> None:
    """Run GOAL replay and Monolithic-LP sweeps for an NSYS-derived input."""
    if args.trace_root is None:
        return
    goal = analysis / "output.goal"
    comm_dep = out_dir / "comm_dep.csv"
    common_topology: list[object] = [
        "--ranks-per-node",
        "4",
        "--L-intra",
        "350",
        "--G-intra",
        "0.00333",
    ]
    records.append(
        run(
            [
                PYTHON,
                "pipeline/run_lgs.py",
                "--goal",
                goal,
                "--L",
                "4000",
                "--G",
                "0.04",
                "--o",
                "200",
                "--comm-dep-out",
                comm_dep,
                "--bin-cache-dir",
                out_dir / "bin_cache",
                *common_topology,
            ],
            timeout=3600,
        )
    )
    records.append(
        run(
            [
                PYTHON,
                "pipeline/run_lgs_sweep.py",
                "--goal",
                goal,
                "--out",
                out_dir / "lgs_runtime.csv",
                "--latencies",
                *[str(value) for value in range(0, 1_000_001, 50_000)],
                "--G",
                "0.04",
                "--o",
                "200",
                "--bin-cache-dir",
                out_dir / "bin_cache",
                *common_topology,
            ],
            timeout=3600,
        )
    )
    lp_topology: list[object] = [
        "--ranks-per-node",
        "4",
        "--l-intra",
        "350",
        "--g-intra",
        "0.00333",
    ]
    if add_barriers:
        lp_topology.append("--add-barriers")
    if nic_per_rank:
        lp_topology += ["--nic-per-rank", "--nics-per-node", "4"]
    records.append(
        run(
            [
                PYTHON,
                "pipeline/run_monolithic_lp.py",
                "--goal",
                goal,
                "--comm-dep",
                comm_dep,
                "--out",
                out_dir / "monolithic_runtime.csv",
                "--l-min",
                "0",
                "--l-max",
                "1000000",
                "--step",
                "5000",
                "--G",
                "0.04",
                "--o",
                "200",
                *lp_topology,
            ],
            timeout=3600,
        )
    )
    records.append(
        run(
            [
                PYTHON,
                "pipeline/run_monolithic_bandwidth_points.py",
                "--goal",
                goal,
                "--comm-dep",
                comm_dep,
                "--out",
                out_dir / "monolithic_bandwidth.csv",
                "--gaps",
                *[f"{index * 0.002:.3f}" for index in range(61)],
                "--fixed-L",
                "3700",
                "--o",
                "200",
                "--threads",
                args.workers,
                *lp_topology,
            ],
            timeout=3600,
        )
    )


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
    for name, packaged_analysis, extra in specs:
        analysis = analysis_input(
            args,
            records,
            trace_subdir=f"fig3/{name}",
            packaged=packaged_analysis,
        )
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
        bw_extra = list(extra)
        if "--disable-intra-node-transfer" in bw_extra:
            bw_extra.remove("--disable-intra-node-transfer")
            bw_extra.append("--no-enable-intra-node-transfer")
        fresh_bandwidth = out_dir / "bandwidth_sensitivity.csv"
        records.append(
            run(
                bandwidth_command(
                    analysis,
                    fresh_bandwidth,
                    out_dir / "bandwidth_cache",
                    args.workers,
                    bw_extra,
                )
            )
        )
        raw_monolithic_outputs(
            args,
            records,
            analysis=analysis,
            out_dir=out_dir,
            nic_per_rank=(name == "auto"),
        )
    return records


def task_fig4(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig4"
    actual = out_dir / "composed_runtime.csv"
    packaged_analysis = ROOT / "data/output/final_plots/data/mixed_16n_ch1"
    records: list[dict[str, object]] = []
    analysis = analysis_input(
        args,
        records,
        trace_subdir="fig4",
        packaged=packaged_analysis,
    )
    records.append(
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
    )
    records.append(
        run(
            bandwidth_command(
                analysis,
                out_dir / "bandwidth_sensitivity.csv",
                out_dir / "bandwidth_cache",
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
    )
    raw_monolithic_outputs(
        args,
        records,
        analysis=analysis,
        out_dir=out_dir,
        add_barriers=True,
    )
    return records


def task_fig5(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig5"
    command: list[object] = [
        "env",
        f"ARTIFACT_PYTHON={PYTHON}",
        "bash",
        "pipeline/reproduce_fig5_from_nsys.sh",
        "--work",
        out_dir,
        "--workers",
        args.workers,
    ]
    if args.trace_root is not None:
        command += ["--nsys-dir", args.trace_root / "fig5"]
    return [run(command, timeout=3600)]


def task_fig6_latency(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig6_latency"
    actual = out_dir / "composed_runtime.csv"
    records: list[dict[str, object]] = []
    analysis = analysis_input(
        args,
        records,
        trace_subdir="fig6/llama",
        packaged=ROOT / "data/workspaces/llama7b_n32_spcl_20260407/analysis",
    )
    records.append(
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
    )
    return records


def task_fig6_bandwidth(args: argparse.Namespace) -> list[dict[str, object]]:
    out_dir = args.scratch / "fig6_bandwidth"
    actual = out_dir / "bandwidth_sensitivity.csv"
    records: list[dict[str, object]] = []
    analysis = analysis_input(
        args,
        records,
        trace_subdir="fig6/llama",
        packaged=ROOT / "data/workspaces/llama7b_n32_spcl_20260407/analysis",
    )
    records.append(
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
    return [
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


def task_grok4096_bandwidth(args: argparse.Namespace) -> list[dict[str, object]]:
    analysis = require_grok_analysis(args)
    out_dir = args.scratch / "grok4096_bandwidth"
    actual = out_dir / "bandwidth_sensitivity.csv"
    return [
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


def task_plots(args: argparse.Namespace) -> list[dict[str, object]]:
    return [
        run(
            [
                PYTHON,
                "scripts/plot_full_run.py",
                "--scratch",
                args.scratch,
            ],
            timeout=900,
        )
    ]


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
    "plots": task_plots,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=sorted(TASKS))
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--grok-analysis-dir", type=Path)
    parser.add_argument("--trace-root", type=Path)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    args.scratch = args.scratch.resolve()
    args.scratch.mkdir(parents=True, exist_ok=True)
    if args.trace_root is not None:
        args.trace_root = args.trace_root.resolve()

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
            "input_stage": (
                "nsys"
                if args.task == "fig5"
                or (
                    args.trace_root is not None
                    and args.task in {"fig3", "fig4", "fig6-latency", "fig6-bandwidth"}
                )
                else "trace-derived inputs"
            ),
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
