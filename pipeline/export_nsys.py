#!/usr/bin/env python3
"""Export a directory of NSYS reports to SQLite in parallel.

The input directory may contain reports in nested subdirectories. SQLite
files are placed directly in the output directory for the NCCL generator.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
from pathlib import Path


def export_one(report: Path, output_dir: Path, nsys: str) -> Path:
    output = output_dir / report.with_suffix(".sqlite").name
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size:
        return output
    subprocess.run(
        [
            nsys,
            "export",
            "--type=sqlite",
            "--force-overwrite=true",
            f"--output={output}",
            str(report),
        ],
        check=True,
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--nsys", default=os.environ.get("NSYS_BIN", "nsys"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    reports = sorted(input_dir.rglob("*.nsys-rep"))
    if not reports:
        parser.error(f"no .nsys-rep files found below {input_dir}")
    if args.workers < 1:
        parser.error("--workers must be positive")
    names = [report.with_suffix(".sqlite").name for report in reports]
    if len(names) != len(set(names)):
        parser.error("duplicate NSYS basenames would overwrite SQLite outputs")
    if (
        not args.dry_run
        and shutil.which(args.nsys) is None
        and not Path(args.nsys).is_file()
    ):
        parser.error(f"NSYS executable not found: {args.nsys}")

    print(f"reports: {len(reports)}")
    print(f"input:   {input_dir}")
    print(f"output:  {output_dir}")
    if args.dry_run:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(export_one, report, output_dir, args.nsys)
            for report in reports
        ]
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
