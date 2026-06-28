#!/usr/bin/env python3
"""Build compact summaries for the final scratch rerun campaign."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_time_log(path: Path) -> tuple[int | None, str | None, int | None]:
    if not path.exists():
        return None, None, None
    text = path.read_text(encoding="utf-8", errors="replace")
    rss = None
    elapsed = None
    exit_status = None
    m = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
    if m:
        rss = int(m.group(1))
    m = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*(.+)", text)
    if m:
        elapsed = m.group(1).strip()
    m = re.search(r"Exit status:\s*(\d+)", text)
    if m:
        exit_status = int(m.group(1))
    return rss, elapsed, exit_status


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def load_manifest(results_dir: Path) -> dict[str, Any]:
    return json.loads((results_dir / "manifest.json").read_text(encoding="utf-8"))


def comparison_rows(results_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((results_dir / "comparisons").glob("*/*_summary.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "label": payload.get("label", path.parent.name),
            "n_points": payload.get("n_points"),
            "min_L": payload.get("min_L"),
            "max_L": payload.get("max_L"),
            "max_abs_diff_ns": payload.get("max_abs_diff_ns"),
            "mean_abs_diff_ns": payload.get("mean_abs_diff_ns"),
            "max_abs_rel_diff_pct": payload.get("max_abs_rel_diff_pct"),
            "mean_abs_rel_diff_pct": payload.get("mean_abs_rel_diff_pct"),
            "summary": str(path),
        })
    return rows


def task_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in manifest.get("records", []):
        log = Path(rec.get("log", ""))
        rss, timed_elapsed, exit_status = parse_time_log(log)
        rows.append({
            "name": rec.get("name"),
            "status": rec.get("status"),
            "returncode": rec.get("returncode"),
            "elapsed_s": rec.get("elapsed_s"),
            "timed_elapsed": timed_elapsed or rec.get("timed_elapsed"),
            "max_rss_kib": rss if rss is not None else rec.get("max_rss_kib"),
            "max_rss_gib": (rss / (1024 * 1024)) if rss is not None else "",
            "exit_status_from_time": exit_status,
            "log": str(log),
        })
    return rows


def manual_lgs_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    run_root = Path(manifest.get("run_root", ""))
    if not run_root:
        return []
    rows: list[dict[str, Any]] = []
    for node_count in [128, 256]:
        csv_path = run_root / "grok" / "output" / f"grok_n{node_count}" / "lgs" / "sweeps" / "lgs_runtime.csv"
        log_path = run_root / "manual_logs" / f"grok_N{node_count}_lgs_fresh_patched_tmp.log"
        rss, timed_elapsed, exit_status = parse_time_log(log_path)
        status = "missing"
        row_count = 0
        min_latency = ""
        max_latency = ""
        runtime_ms_min = ""
        runtime_ms_max = ""
        if csv_path.exists() and csv_path.stat().st_size > 0:
            try:
                with csv_path.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    csv_rows = list(reader)
                row_count = len(csv_rows)
                latencies = [float(r["L_ns"]) for r in csv_rows if r.get("L_ns") not in (None, "")]
                runtimes = [float(r["runtime_ms"]) for r in csv_rows if r.get("runtime_ms") not in (None, "")]
                if latencies:
                    min_latency = min(latencies)
                    max_latency = max(latencies)
                if runtimes:
                    runtime_ms_min = min(runtimes)
                    runtime_ms_max = max(runtimes)
                status = "complete" if row_count >= 6 else "partial"
            except Exception as exc:
                status = f"error:{exc}"
        if exit_status not in (None, 0) and status == "complete":
            status = f"csv_complete_log_exit_{exit_status}"
        rows.append({
            "name": f"manual_grok_N{node_count}_lgs_fresh_patched_tmp",
            "status": status,
            "rows": row_count,
            "min_L_ns": min_latency,
            "max_L_ns": max_latency,
            "runtime_ms_min": runtime_ms_min,
            "runtime_ms_max": runtime_ms_max,
            "timed_elapsed": timed_elapsed,
            "max_rss_kib": rss if rss is not None else "",
            "max_rss_gib": (rss / (1024 * 1024)) if rss is not None else "",
            "exit_status_from_time": exit_status,
            "csv": str(csv_path),
            "log": str(log_path) if log_path.exists() else "",
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: Any) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.6g}%"


def fmt_s(value: Any) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.1f}"


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(lines)


def find_row(rows: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("label") == label), None)


def write_report(
    results_dir: Path,
    tasks: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    manual_lgs: list[dict[str, Any]],
) -> None:
    task_map = {row["name"]: row for row in tasks}
    failed = [row for row in tasks if row.get("status") != "ok"]
    preferred_labels = [
        "llama_n32_composite_vs_packaged",
        "llama_n32_bandwidth_vs_packaged",
        "fig03_ch1_vs_packaged",
        "fig03_auto_vs_packaged",
        "fig04_mixed_vs_packaged",
        "fig5_mono_vs_packaged",
        "fig5_historical_composite_vs_old_dev",
        "fig5_historical_composite_vs_packaged",
    ]
    all_labels = [str(row.get("label", "")) for row in comparisons]
    comparison_labels = preferred_labels + [
        label
        for label in sorted(all_labels)
        if label and label not in preferred_labels
    ]
    comparison_rows_md = []
    for label in comparison_labels:
        row = find_row(comparisons, label)
        if row is None:
            comparison_rows_md.append([label, "missing", "", "", ""])
            continue
        comparison_rows_md.append([
            label,
            row.get("n_points"),
            f"{float(row.get('max_abs_diff_ns', 0.0)):.6g}",
            fmt_pct(row.get("max_abs_rel_diff_pct")),
            fmt_pct(row.get("mean_abs_rel_diff_pct")),
        ])

    lines = [
        "# Final Scratch Rerun Summary",
        "",
        f"Repository: `{ROOT}`",
        "",
        f"Branch: `{git_value(['rev-parse', '--abbrev-ref', 'HEAD'])}`",
        "",
        f"Commit: `{git_value(['rev-parse', 'HEAD'])}`",
        "",
        f"Results directory: `{results_dir}`",
        "",
        "Command used for the main campaign:",
        "",
        "```bash",
        "python3 scripts/final_scratch_rerun_campaign.py --workers 8",
        "```",
        "",
        "The campaign starts from existing GOAL, NCCL metadata sidecars, and NSYS/SQLite inputs. It deliberately writes fresh solver caches, `comm_dep.csv` files, LGS binary caches, and outputs under the scratch root instead of reusing packaged scientific CSVs as model results.",
        "",
        "## Campaign Status",
        "",
        f"Tasks recorded: `{len(tasks)}`.",
        "",
        f"Non-OK tasks: `{len(failed)}`.",
        "",
    ]
    if failed:
        lines.append(markdown_table(
            ["Task", "Status", "Return code", "Elapsed s", "Log"],
            [
                [
                    row["name"],
                    row["status"],
                    row["returncode"],
                    fmt_s(row["elapsed_s"]),
                    row["log"],
                ]
                for row in failed
            ],
        ))
        lines.append("")
    lines.extend([
        "## Key Task Timings",
        "",
        markdown_table(
            ["Task", "Status", "Elapsed s", "Max RSS GiB"],
            [
                [
                    name,
                    task_map.get(name, {}).get("status", "missing"),
                    fmt_s(task_map.get(name, {}).get("elapsed_s")),
                    (
                        f"{float(task_map[name]['max_rss_gib']):.3f}"
                        if name in task_map and task_map[name].get("max_rss_gib") != ""
                        else ""
                    ),
                ]
                for name in [
                    "packaged_reproduce_all",
                    "demo_pipeline_reproduce_all",
                    "pytest",
                    "llama_n32_composite_cold",
                    "llama_n32_bandwidth_cold",
                    "fig5_nsys_to_monolithic",
                    "vllm_regenerate_from_sqlite",
                    "vllm_composite_lp",
                    "grok_N64_composite_cold",
                    "grok_N128_composite_cold",
                    "grok_N256_composite_cold",
                    "grok_N512_composite_cold",
                    "grok_N256_lgs_fresh",
                    "grok_N64_monolithic_point_fresh",
                    "grok_node_scaling_plot_fresh_outputs",
                ]
            ],
        ),
        "",
        "## Manual Patched LGS Reruns",
        "",
        "These reruns were launched after fixing large temporary `txt2bin` output placement; they are outside the campaign manifest and are summarized from fresh CSV/log files.",
        "",
        markdown_table(
            ["Task", "Status", "Rows", "Min L ns", "Max L ns", "Elapsed", "Max RSS GiB", "CSV"],
            [
                [
                    row["name"],
                    row["status"],
                    row["rows"],
                    row["min_L_ns"],
                    row["max_L_ns"],
                    row["timed_elapsed"],
                    (
                        f"{float(row['max_rss_gib']):.3f}"
                        if row.get("max_rss_gib") != ""
                        else ""
                    ),
                    row["csv"],
                ]
                for row in manual_lgs
            ],
        ),
        "",
        "## Numeric Comparisons",
        "",
        markdown_table(
            ["Comparison", "Points", "Max abs diff ns", "Max rel diff", "Mean rel diff"],
            comparison_rows_md,
        ),
        "",
        "## Interpretation Notes",
        "",
        "- `fig5_nsys_to_monolithic` can be non-OK even when GOAL, `comm_dep.csv`, and `full_runtime.csv` are generated; the wrapper exits nonzero when the regenerated curve differs from the shipped historical baseline beyond tolerance.",
        "- Composite-LP tasks in this campaign use `--clear-cache` and write fresh solver caches under the scratch root.",
        "- Large LGS runs use scratch-backed `--tmp-dir`/`--bin-cache-dir` paths so binary conversion does not exhaust `/tmp`.",
        "- Large GOAL files, SQLite exports, binary caches, and LP sidecars remain under the scratch root; only compact summaries are written here.",
        "",
        "## Grok Scaling Plot Outputs",
        "",
        f"- Repository plot directory: `{results_dir / 'grok_node_scaling'}`",
        f"- New-results mirror: `{ROOT / 'new_results' / 'final_scratch_rerun_20260627'}`",
        "- Regenerate after long-running LGS/Monolithic jobs finish with:",
        "",
        "```bash",
        "python3 scripts/grok_node_scaling.py \\",
        "  --scratch-root /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok \\",
        "  --extra-scratch-root /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok \\",
        "  --out-dir results/final_scratch_rerun_20260627/grok_node_scaling \\",
        "  --nodes 4 8 16 32 64 128 256 512 \\",
        "  --target-latency 0 \\",
        "  --target-latencies 0 4000 10000 250000 500000 1000000 \\",
        "  --no-packaged-large --include-legacy-monolithic",
        "```",
        "",
        "## Generated Files",
        "",
        f"- Task CSV: `{results_dir / 'task_summary.csv'}`",
        f"- Comparison CSV: `{results_dir / 'comparison_summary.csv'}`",
        f"- Manual LGS CSV: `{results_dir / 'manual_lgs_summary.csv'}`",
        f"- Manifest: `{results_dir / 'manifest.json'}`",
        f"- Campaign report: `{results_dir / 'report.md'}`",
    ])
    (results_dir / "final_scratch_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results" / "final_scratch_rerun_20260627")
    args = ap.parse_args()
    manifest = load_manifest(args.results_dir)
    tasks = task_rows(manifest)
    comparisons = comparison_rows(args.results_dir)
    manual_lgs = manual_lgs_rows(manifest)
    write_csv(args.results_dir / "task_summary.csv", tasks)
    write_csv(args.results_dir / "comparison_summary.csv", comparisons)
    write_csv(args.results_dir / "manual_lgs_summary.csv", manual_lgs)
    write_report(args.results_dir, tasks, comparisons, manual_lgs)
    print(f"[summary] wrote {args.results_dir / 'task_summary.csv'}")
    print(f"[summary] wrote {args.results_dir / 'comparison_summary.csv'}")
    print(f"[summary] wrote {args.results_dir / 'manual_lgs_summary.csv'}")
    print(f"[summary] wrote {args.results_dir / 'final_scratch_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
