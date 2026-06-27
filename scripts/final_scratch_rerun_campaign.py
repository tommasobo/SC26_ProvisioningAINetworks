#!/usr/bin/env python3
"""Run a fresh-cache final revalidation campaign.

The campaign intentionally starts from existing GOAL, metadata, and NSYS files,
not from cached solver outputs. Heavy per-run caches, sidecars, and logs are
kept under ``--run-root``. Small comparison summaries and the final report are
written under ``--repo-results``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


@dataclass
class Record:
    name: str
    cmd: list[str]
    timeout_s: int | None
    returncode: int | None
    elapsed_s: float
    log: str
    status: str
    max_rss_kib: int | None = None
    timed_elapsed: str | None = None
    note: str = ""
    outputs: dict[str, Any] = field(default_factory=dict)


class Campaign:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.run_root = args.run_root.resolve()
        self.repo_results = args.repo_results.resolve()
        self.logs = self.run_root / "logs"
        self.records: list[Record] = []
        self.started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.repo_results.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        (self.run_root / "caches").mkdir(exist_ok=True)
        (self.run_root / "bin_cache").mkdir(exist_ok=True)

    def save_state(self) -> None:
        payload = {
            "started_utc": self.started_utc,
            "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repo": str(ROOT),
            "branch": self._git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "commit": self._git(["rev-parse", "HEAD"]),
            "run_root": str(self.run_root),
            "repo_results": str(self.repo_results),
            "records": [r.__dict__ for r in self.records],
        }
        (self.repo_results / "manifest.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.write_report(payload)

    def _git(self, args: list[str]) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        except Exception:
            return ""

    def parse_time_log(self, text: str) -> tuple[int | None, str | None]:
        rss = None
        elapsed = None
        m = re.search(r"Maximum resident set size \\(kbytes\\):\\s*(\\d+)", text)
        if m:
            rss = int(m.group(1))
        m = re.search(r"Elapsed \\(wall clock\\) time.*:\\s*(.+)", text)
        if m:
            elapsed = m.group(1).strip()
        return rss, elapsed

    def run(
        self,
        name: str,
        cmd: list[str],
        timeout_s: int | None,
        *,
        cwd: Path = ROOT,
        note: str = "",
        outputs: dict[str, Any] | None = None,
    ) -> Record:
        log_path = self.logs / f"{name}.log"
        wrapped = ["/usr/bin/time", "-v"]
        if timeout_s is not None:
            wrapped += ["timeout", str(timeout_s)]
        wrapped += cmd
        print(f"[campaign] START {name}", flush=True)
        print("  " + " ".join(str(x) for x in cmd), flush=True)
        t0 = time.perf_counter()
        with log_path.open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(str(x) for x in wrapped) + "\n\n")
            log.flush()
            proc = subprocess.run(
                [str(x) for x in wrapped],
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        elapsed_s = time.perf_counter() - t0
        text = log_path.read_text(encoding="utf-8", errors="replace")
        rss, timed_elapsed = self.parse_time_log(text)
        if proc.returncode == 0:
            status = "ok"
        elif proc.returncode == 124:
            status = "timeout"
        else:
            status = "failed"
        rec = Record(
            name=name,
            cmd=[str(x) for x in cmd],
            timeout_s=timeout_s,
            returncode=proc.returncode,
            elapsed_s=elapsed_s,
            log=str(log_path),
            status=status,
            max_rss_kib=rss,
            timed_elapsed=timed_elapsed,
            note=note,
            outputs=outputs or {},
        )
        self.records.append(rec)
        self.save_state()
        print(f"[campaign] END {name}: {status} in {elapsed_s:.1f}s", flush=True)
        return rec

    def compare(
        self,
        name: str,
        expected: Path,
        actual: Path,
        *,
        points: str = "actual",
        expected_x: str | None = None,
        expected_y: str | None = None,
        actual_x: str | None = None,
        actual_y: str | None = None,
    ) -> None:
        out_dir = self.repo_results / "comparisons" / name
        cmd = [
            PY,
            "scripts/compare_csv.py",
            "--expected",
            str(expected),
            "--actual",
            str(actual),
            "--out-dir",
            str(out_dir),
            "--label",
            name,
            "--points",
            points,
        ]
        if expected_x:
            cmd += ["--expected-x-col", expected_x]
        if expected_y:
            cmd += ["--expected-y-col", expected_y]
        if actual_x:
            cmd += ["--actual-x-col", actual_x]
        if actual_y:
            cmd += ["--actual-y-col", actual_y]
        self.run(f"compare_{name}", cmd, 600)

    def safe_link(self, src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() or dst.is_symlink():
            return
        os.symlink(src, dst)

    def copy_small(self, src: Path, dst: Path, max_bytes: int = 10_000_000) -> None:
        if not src.exists() or not src.is_file():
            return
        if src.stat().st_size > max_bytes:
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    def write_report(self, payload: dict[str, Any]) -> None:
        report = self.repo_results / "report.md"
        lines = [
            "# Final Scratch Rerun Report",
            "",
            f"Updated UTC: `{payload['updated_utc']}`",
            "",
            f"Branch: `{payload.get('branch', '')}`",
            "",
            f"Commit: `{payload.get('commit', '')}`",
            "",
            f"Scratch root: `{self.run_root}`",
            "",
            "## Task Status",
            "",
            "| Task | Status | Elapsed s | Max RSS GiB | Log |",
            "| --- | --- | ---: | ---: | --- |",
        ]
        for rec in self.records:
            rss_gib = ""
            if rec.max_rss_kib is not None:
                rss_gib = f"{rec.max_rss_kib / (1024 * 1024):.3f}"
            rel_log = Path(rec.log)
            lines.append(
                f"| `{rec.name}` | `{rec.status}` | {rec.elapsed_s:.1f} | {rss_gib} | `{rel_log}` |"
            )
        lines.extend([
            "",
            "## Notes",
            "",
            "- Commands use fresh cache/output directories under the scratch root.",
            "- Large sidecars, txt2bin caches, and solver caches are not copied into the repo.",
            "- Small comparison JSON/CSV summaries are under `comparisons/`.",
        ])
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_core_tasks(c: Campaign) -> None:
    c.run("packaged_reproduce_all", [PY, "reproduce_all.py"], 7200)
    c.run("demo_pipeline_reproduce_all", [PY, "reproduce_all.py", "--pipeline"], 7200)
    pytest_py = ROOT / ".venv" / "bin" / "python"
    if pytest_py.exists():
        c.run("pytest", [str(pytest_py), "-m", "pytest", "-q"], 1800)
    else:
        c.run("pytest", [PY, "-m", "pytest", "-q"], 1800)


def add_llama_n32_tasks(c: Campaign) -> None:
    out = c.run_root / "llama_n32"
    comp_csv = out / "composite" / "comp" / "sweeps" / "composed_runtime.csv"
    cache = out / "composite_cache"
    c.run(
        "llama_n32_composite_cold",
        [
            PY,
            "pipeline/run_nccl_composite.py",
            "--analysis-dir",
            "data/workspaces/llama7b_n32_spcl_20260407/analysis",
            "--out",
            str(comp_csv),
            "--cache-dir",
            str(cache),
            "--clear-cache",
            "--parallel-solve",
            "--max-workers",
            str(c.args.workers),
            "--node-map-mode",
            "rank-block",
            "--force-sequential",
            "--nic-per-rank",
        ],
        7200,
    )
    c.compare(
        "llama_n32_composite_vs_packaged",
        ROOT / "data/workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/composed_runtime.csv",
        comp_csv,
    )

    bw_csv = out / "bandwidth" / "bandwidth_sensitivity.csv"
    c.run(
        "llama_n32_bandwidth_cold",
        [
            PY,
            "pipeline/run_nccl_bw_sensitivity.py",
            "--analysis-dir",
            "data/workspaces/llama7b_n32_spcl_20260407/analysis",
            "--out",
            str(bw_csv),
            "--cache-dir",
            str(out / "bandwidth_cache"),
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
            str(c.args.workers),
            "--node-map-mode",
            "rank-block",
            "--force-sequential",
            "--nic-per-rank",
        ],
        7200,
    )
    c.compare(
        "llama_n32_bandwidth_vs_packaged",
        ROOT / "data/workspaces/llama7b_n32_spcl_20260407/output/bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv",
        bw_csv,
        expected_x="bw_gbps",
        actual_x="bw_gbps",
        expected_y="runtime_ns",
        actual_y="runtime_ns",
    )


def add_fig34_tasks(c: Campaign) -> None:
    specs = [
        (
            "fig03_ch1",
            "data/output/final_plots/data/ar_128m_16n_ch1",
            ROOT / "data/output/final_plots/data/ar_128m_16n_ch1/latency_compressed_runtime.csv",
            ["--node-map-mode", "rank-block", "--ring-duplicate-policy", "last", "--disable-intra-node-transfer"],
        ),
        (
            "fig03_auto",
            "data/output/final_plots/data/ar_128m_16n_auto",
            ROOT / "data/output/final_plots/data/ar_128m_16n_auto/latency_compressed_runtime.csv",
            ["--program-rank", "6", "--node-map-mode", "rank-block", "--ring-duplicate-policy", "last", "--nic-per-rank", "--force-sequential"],
        ),
        (
            "fig04_mixed",
            "data/output/final_plots/data/mixed_16n_ch1",
            ROOT / "data/output/final_plots/data/mixed_16n_ch1/latency_full_runtime.csv",
            ["--node-map-mode", "rank-block", "--ring-duplicate-policy", "last", "--nic-per-rank", "--force-sequential"],
        ),
    ]
    for name, analysis, expected, extra in specs:
        out = c.run_root / "fig34" / name
        actual = out / "comp" / "sweeps" / "composed_runtime.csv"
        c.run(
            f"{name}_composite_cold",
            [
                PY,
                "pipeline/run_nccl_composite.py",
                "--analysis-dir",
                analysis,
                "--out",
                str(actual),
                "--cache-dir",
                str(out / "collective_cache"),
                "--clear-cache",
                "--parallel-solve",
                "--max-workers",
                str(max(2, min(c.args.workers, 4))),
                *extra,
            ],
            7200,
        )
        c.compare(f"{name}_vs_packaged", expected, actual)


def add_fig5_tasks(c: Campaign) -> None:
    fig5 = c.run_root / "fig5_from_nsys"
    raw = Path("/mnt/scratch/LLAMA/Traces_Compression/workspaces/llama7b_n4_spcl_20260407/raw_nsys")
    for rep in sorted(raw.glob("*.nsys-rep")):
        c.safe_link(rep, fig5 / "nsys" / rep.name)
    c.run(
        "fig5_nsys_to_monolithic",
        [
            "bash",
            "pipeline/reproduce_fig5_from_nsys.sh",
            "--skip-download",
            "--work",
            str(fig5),
            "--run-lp",
        ],
        7200,
    )
    c.compare(
        "fig5_mono_vs_packaged",
        ROOT / "data/output/llama7b/partial_100pct/sweeps/full_runtime.csv",
        fig5 / "out" / "full_runtime.csv",
    )
    hist_csv = c.run_root / "fig5_composite_historical" / "composed_runtime.csv"
    c.run(
        "fig5_composite_historical_cold",
        [
            PY,
            "pipeline/run_nccl_composite.py",
            "--analysis-dir",
            str(fig5 / "analysis"),
            "--out",
            str(hist_csv),
            "--cache-dir",
            str(c.run_root / "fig5_composite_historical" / "cache"),
            "--clear-cache",
            "--generator-dir",
            "/mnt/scratch/LLAMA/Traces_Compression/tools/nccl_generator_v2_hwfix",
            "--npkit-simple",
            "/mnt/scratch/LLAMA/Traces_Compression/reference_bundle/npkit_results/simple_1ch/npkit_data_summary_Simple_alps.json",
            "--npkit-ll",
            "/mnt/scratch/LLAMA/Traces_Compression/reference_bundle/npkit_results/ll_1ch/npkit_data_summary_LL_alps.json",
            "--node-map-mode",
            "rank-block",
            "--ring-duplicate-policy",
            "last",
            "--nic-per-rank",
            "--parallel-solve",
            "--max-workers",
            str(c.args.workers),
            "--l-min",
            "0",
            "--l-max",
            "1000000",
            "--step",
            "5000",
        ],
        1800,
    )
    c.compare(
        "fig5_historical_composite_vs_old_dev",
        Path("/mnt/scratch/LLAMA/Traces_Compression/workspaces/llama7b_n4_spcl_20260407/output/comp/sweeps/composed_runtime.csv"),
        hist_csv,
    )
    c.compare(
        "fig5_historical_composite_vs_packaged",
        ROOT / "data/output/llama7b/comp_100pct/sweeps/composed_runtime.csv",
        hist_csv,
    )


def add_vllm_tasks(c: Campaign) -> None:
    vllm = c.run_root / "vllm_online_nsys"
    sqlite = vllm / "sqlite"
    sqlite.mkdir(parents=True, exist_ok=True)
    for rep in sorted(Path("/mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/nsys").glob("*.nsys-rep")):
        out_sqlite = sqlite / f"{rep.stem}.sqlite"
        c.run(
            f"vllm_nsys_export_{rep.stem}",
            ["nsys", "export", "--type=sqlite", "-o", str(out_sqlite), str(rep)],
            1800,
        )
    driver = vllm / "driver"
    c.run(
        "vllm_regenerate_from_sqlite",
        [
            PY,
            "pipeline/regenerate_from_inputs.py",
            "--sqlite-dir",
            str(sqlite),
            "--out-dir",
            str(driver),
            "--L-sidecar",
            "4000",
            "--G",
            "0.04",
            "--o",
            "200",
            "--lgs-latencies",
            "0",
            "4000",
            "10000",
            "--bin-cache-dir",
            str(c.run_root / "bin_cache" / "vllm"),
        ],
        3600,
    )
    comp = vllm / "composite_lp" / "composed_runtime.csv"
    c.run(
        "vllm_composite_lp",
        [
            PY,
            "pipeline/run_composite_lp.py",
            "--goal",
            str(driver / "analysis" / "output.goal"),
            "--comm-dep",
            str(driver / "comm_dep.csv"),
            "--out",
            str(comp),
            "--l-min",
            "0",
            "--l-max",
            "10000",
            "--step",
            "5000",
            "--l-intra",
            "350",
            "--o",
            "200",
        ],
        3600,
    )


def grok_analysis(node: int) -> Path:
    return Path(f"/mnt/scratch/GrokStudyCodex/Traces_Compression/workspaces/grok/N{node}/analysis")


def add_grok_composite_tasks(c: Campaign) -> None:
    grok_root = c.run_root / "grok"
    for node in [4, 8, 16, 32, 64, 128, 256, 512]:
        analysis = grok_analysis(node)
        c.safe_link(analysis, grok_root / "workspaces" / "grok" / f"N{node}" / "analysis")
        actual = grok_root / "output" / f"grok_n{node}" / "comp" / "sweeps" / "composed_runtime.csv"
        c.run(
            f"grok_N{node}_composite_cold",
            [
                PY,
                "pipeline/run_nccl_composite.py",
                "--analysis-dir",
                str(analysis),
                "--out",
                str(actual),
                "--cache-dir",
                str(grok_root / "output" / f"grok_n{node}" / "collective_cache"),
                "--clear-cache",
                "--parallel-solve",
                "--max-workers",
                str(max(2, min(c.args.workers, 4))),
                "--l-min",
                "0",
                "--l-max",
                "1000000",
                "--step",
                "5000",
            ],
            14400 if node >= 512 else 7200,
        )
        expected = Path(f"/mnt/scratch/GrokStudyCodex/Traces_Compression/output/grok_n{node}/comp/sweeps/composed_runtime.csv")
        if expected.exists():
            c.compare(f"grok_N{node}_composite_vs_development", expected, actual)


def add_grok_lgs_tasks(c: Campaign) -> None:
    grok_root = c.run_root / "grok"
    for node in [4, 8, 16, 32, 64, 128, 256]:
        goal = grok_analysis(node) / "output.goal"
        out = grok_root / "output" / f"grok_n{node}" / "lgs" / "sweeps" / "lgs_runtime.csv"
        c.run(
            f"grok_N{node}_lgs_fresh",
            [
                PY,
                "pipeline/run_lgs_sweep.py",
                "--goal",
                str(goal),
                "--out",
                str(out),
                "--latencies",
                "0",
                "4000",
                "10000",
                "250000",
                "500000",
                "1000000",
                "--G",
                "0.04",
                "--o",
                "200",
                "--normalize-tags",
                "never",
                "--bin-cache-dir",
                str(c.run_root / "bin_cache" / f"grok_lgs_N{node}"),
            ],
            21600 if node >= 128 else 7200,
        )


def add_grok_monolithic_tasks(c: Campaign) -> None:
    grok_root = c.run_root / "grok"
    for node, timeout_s in [(4, 3600), (8, 7200), (16, 7200), (32, 14400), (64, 21600)]:
        out_dir = grok_root / "output" / f"grok_n{node}" / "monolithic_regen"
        c.run(
            f"grok_N{node}_monolithic_point_fresh",
            [
                PY,
                "pipeline/regenerate_from_inputs.py",
                "--goal",
                str(grok_analysis(node) / "output.goal"),
                "--out-dir",
                str(out_dir),
                "--L-sidecar",
                "4000",
                "--G",
                "0.04",
                "--o",
                "200",
                "--monolithic-latencies",
                "4000",
                "--bin-cache-dir",
                str(c.run_root / "bin_cache" / f"grok_mono_N{node}"),
            ],
            timeout_s,
        )
        points = out_dir / "monolithic_points.csv"
        if points.exists():
            target = grok_root / "output" / f"grok_n{node}" / "monolithic" / "sweeps" / "full_runtime.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(points, target)


def add_grok_plot_task(c: Campaign) -> None:
    out_dir = c.repo_results / "grok_node_scaling"
    c.run(
        "grok_node_scaling_plot_fresh_outputs",
        [
            PY,
            "scripts/grok_node_scaling.py",
            "--scratch-root",
            str(c.run_root / "grok"),
            "--extra-scratch-root",
            str(c.run_root / "grok"),
            "--out-dir",
            str(out_dir),
            "--nodes",
            "4",
            "8",
            "16",
            "32",
            "64",
            "128",
            "256",
            "512",
            "--target-latency",
            "0",
            "--target-latencies",
            "0",
            "4000",
            "10000",
            "250000",
            "500000",
            "1000000",
            "--no-packaged-large",
            "--include-legacy-monolithic",
        ],
        1800,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-root", type=Path, default=Path("/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627"))
    ap.add_argument("--repo-results", type=Path, default=ROOT / "results" / "final_scratch_rerun_20260627")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-grok-lgs", action="store_true")
    ap.add_argument("--skip-grok-monolithic", action="store_true")
    args = ap.parse_args()
    c = Campaign(args)

    add_core_tasks(c)
    add_llama_n32_tasks(c)
    add_fig34_tasks(c)
    add_fig5_tasks(c)
    add_vllm_tasks(c)
    add_grok_composite_tasks(c)
    if not args.skip_grok_lgs:
        add_grok_lgs_tasks(c)
    if not args.skip_grok_monolithic:
        add_grok_monolithic_tasks(c)
    add_grok_plot_task(c)
    c.save_state()
    failed = [r for r in c.records if r.status != "ok"]
    print(f"[campaign] complete: {len(c.records)} tasks, {len(failed)} non-ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
