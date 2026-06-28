#!/usr/bin/env python3
"""
Run LogGOPSim over multiple latency points and write a CSV.

Example:
    python3 pipeline/run_lgs_sweep.py \
        --goal data/traces/demo_allreduce_16r_1MiB.goal \
        --out data/demo_output/lgs_points.csv \
        --latencies 0 1000 10000 100000
"""
import argparse
import csv
import time
from pathlib import Path

from run_lgs import run_lgs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--latencies", nargs="+", type=int, required=True,
                    help="Inter-node latency points in ns.")
    ap.add_argument("--G", type=float, default=0.04,
                    help="Inter-node gap per byte, ns/byte (default: 0.04)")
    ap.add_argument("--o", type=int, default=200,
                    help="Overhead, ns (default: 200)")
    ap.add_argument("--g", type=int, default=5,
                    help="Gap, ns (default: 5)")
    ap.add_argument("--normalize-tags", choices=("auto", "always", "never"), default="auto",
                    help="Forwarded to run_lgs.py.")
    ap.add_argument("--bin-cache-dir", type=Path, default=None,
                    help="Optional local cache directory for txt2bin output.")
    ap.add_argument("--tmp-dir", type=Path, default=None,
                    help="Directory for large temporary txt2bin files. "
                         "Defaults to a sibling of --bin-cache-dir when set, "
                         "otherwise Python's default temp directory.")
    args = ap.parse_args()

    if not args.goal.exists():
        ap.error(f"GOAL file not found: {args.goal}")

    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "L_ns",
        "runtime_ns",
        "runtime_ms",
        "elapsed_s",
        "G_ns_per_byte",
        "o_ns",
        "g_ns",
    ]
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for latency in args.latencies:
            t0 = time.perf_counter()
            runtime_ns = run_lgs(
                args.goal,
                latency,
                args.G,
                args.o,
                args.g,
                normalize_tags=args.normalize_tags,
                bin_cache_dir=args.bin_cache_dir,
                tmp_dir=args.tmp_dir,
            )
            elapsed_s = time.perf_counter() - t0
            writer.writerow({
                "L_ns": latency,
                "runtime_ns": runtime_ns,
                "runtime_ms": runtime_ns / 1e6,
                "elapsed_s": elapsed_s,
                "G_ns_per_byte": args.G,
                "o_ns": args.o,
                "g_ns": args.g,
            })
            f.flush()
            print(
                f"[lgs-sweep] L={latency} ns runtime={runtime_ns} ns "
                f"({runtime_ns / 1e6:.3f} ms), elapsed={elapsed_s:.2f}s"
            )

    print(f"[lgs-sweep] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
