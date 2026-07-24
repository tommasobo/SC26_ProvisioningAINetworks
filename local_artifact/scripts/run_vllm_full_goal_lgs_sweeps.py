#!/usr/bin/env python3
"""Run sampled LogGOPSim latency and bandwidth sweeps on a GOAL-derived BIN."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from pathlib import Path


def simulate(simulator: Path, bin_path: Path, latency: int, gap_per_byte: float) -> int:
    command = [
        str(simulator),
        "-f",
        str(bin_path),
        "--LogGOPS_L",
        str(latency),
        "--LogGOPS_o",
        "200",
        "--LogGOPS_g",
        "5",
        "--LogGOPS_G",
        str(gap_per_byte),
        "--LogGOPS_S",
        "0",
        "-b",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    match = re.search(r"Maximum finishing time at host \d+:\s*(\d+)", result.stdout)
    if not match:
        host_times = [int(value) for value in re.findall(r"Host \d+:\s*(\d+)", result.stdout)]
        if not host_times:
            raise RuntimeError("LogGOPSim output did not contain a host finishing time")
        return max(host_times)
    return int(match.group(1))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", required=True, type=Path)
    parser.add_argument("--simulator", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    latency_points = [0, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 750000, 1000000]
    bandwidth_points = [round(step * 0.01, 3) for step in range(17)]
    started = time.perf_counter()
    latency_rows = [
        {"L": latency, "runtime": simulate(args.simulator, args.bin, latency, 0.04)}
        for latency in latency_points
    ]
    bandwidth_rows = [
        {"G": gap, "runtime": simulate(args.simulator, args.bin, 4000, gap)}
        for gap in bandwidth_points
    ]
    write_csv(args.out / "latency_runtime.csv", ["L", "runtime"], latency_rows)
    write_csv(args.out / "bandwidth_runtime.csv", ["G", "runtime"], bandwidth_rows)
    summary = {
        "bin": str(args.bin.resolve()),
        "simulator": str(args.simulator.resolve()),
        "latency_points": len(latency_rows),
        "bandwidth_points": len(bandwidth_rows),
        "bandwidth_fixed_L_ns": 4000,
        "elapsed_s": time.perf_counter() - started,
        "latency_T0_ns": latency_rows[0]["runtime"],
        "latency_T1M_ns": latency_rows[-1]["runtime"],
        "bandwidth_TG0_ns": bandwidth_rows[0]["runtime"],
        "bandwidth_TGmax_ns": bandwidth_rows[-1]["runtime"],
    }
    (args.out / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
