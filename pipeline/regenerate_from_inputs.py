#!/usr/bin/env python3
"""Regenerate sidecars and selected outputs from GOAL or NSYS SQLite inputs.

This is the artifact's user-facing orchestration path for data-level
regeneration. It does not retrace workloads. It starts from either:

* an existing ``output.goal`` trace, or
* a directory of SQLite files exported from ``nsys``.

For SQLite input, it first runs ``pipeline/run_nccl_generator.py`` to produce
``output.goal`` plus NCCL metadata sidecars. It then generates or validates
the LP ``comm_dep.csv`` sidecar, and optionally runs LogGOPSim sweeps and
Monolithic-LP exact-point or full-sweep solves.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run_cmd(cmd: list[str], *, dry_run: bool, cwd: Path | None = None) -> dict[str, Any]:
    printable = " ".join(cmd)
    print(">>>", printable, flush=True)
    if dry_run:
        return {"cmd": cmd, "cwd": str(cwd) if cwd else None, "returncode": 0, "dry_run": True}
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd)
    elapsed_s = time.perf_counter() - t0
    record = {
        "cmd": cmd,
        "cwd": str(cwd) if cwd else None,
        "returncode": result.returncode,
        "elapsed_s": elapsed_s,
        "dry_run": False,
    }
    if result.returncode != 0:
        raise RuntimeError(f"command failed with code {result.returncode}: {printable}")
    return record


def validate_comm_dep(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"comm_dep file not found: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError(
            f"comm_dep file is empty: {path}. "
            "Patched LogGOPSim did not emit send/recv matches for this GOAL."
        )
    rows = 0
    first_rows: list[list[int]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for lineno, row in enumerate(reader, start=1):
            if len(row) != 4:
                raise ValueError(f"{path}:{lineno}: expected 4 columns, found {len(row)}")
            try:
                parsed = [int(value) for value in row]
            except ValueError as exc:
                raise ValueError(f"{path}:{lineno}: expected integer columns: {row}") from exc
            if any(value < 0 for value in parsed):
                raise ValueError(f"{path}:{lineno}: negative value in comm_dep row: {row}")
            rows += 1
            if len(first_rows) < 3:
                first_rows.append(parsed)
    return {
        "path": str(path),
        "bytes": size,
        "rows": rows,
        "first_rows": first_rows,
    }


def file_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
    }


def fmt_number(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    inputs = ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--goal", type=Path, help="Existing GOAL trace.")
    inputs.add_argument("--sqlite-dir", type=Path,
                        help="Directory of NSYS-exported SQLite files.")
    ap.add_argument("--out-dir", required=True, type=Path,
                    help="Output directory for generated files and manifest.")
    ap.add_argument("--comm-dep", type=Path, default=None,
                    help="Existing comm_dep sidecar to validate and reuse.")
    ap.add_argument("--comm-dep-mode", choices=("auto", "lgs", "goal", "existing"),
                    default="auto",
                    help="How to obtain comm_dep. Default auto uses an existing "
                         "--comm-dep if provided, otherwise patched LogGOPSim.")
    ap.add_argument("--allow-goal-fallback", action="store_true",
                    help="Allow GOAL-only FIFO matching if LogGOPSim sidecar "
                         "generation fails or emits an empty file. This is not "
                         "universally correct; the public prebuilt vLLM "
                         "Llama70B N2 GOAL is a known counterexample.")
    ap.add_argument("--npkit-simple", type=Path, default=None,
                    help="Override NPKit simple calibration JSON for SQLite input.")
    ap.add_argument("--npkit-ll", type=Path, default=None,
                    help="Override NPKit LL calibration JSON for SQLite input.")
    ap.add_argument("--generator-parallel", action="store_true",
                    help="Forward --parallel to run_nccl_generator.py.")
    ap.add_argument("--bin-cache-dir", type=Path, default=None,
                    help="Optional local txt2bin cache directory forwarded to "
                         "LogGOPSim sidecar generation and LGS sweeps.")
    ap.add_argument("--lgs-latencies", nargs="+", type=int, default=None,
                    help="If set, run a LogGOPSim latency sweep at these L values.")
    ap.add_argument("--monolithic-latencies", nargs="+", type=float, default=None,
                    help="If set, run exact-point Monolithic-LP at these L values.")
    ap.add_argument("--run-monolithic-sweep", action="store_true",
                    help="Run full Monolithic-LP sensitivity sweep.")
    ap.add_argument("--l-min", type=int, default=0)
    ap.add_argument("--l-max", type=int, default=1_000_000)
    ap.add_argument("--step", type=int, default=50_000)
    ap.add_argument("--L-sidecar", type=int, default=1000,
                    help="Latency passed to LogGOPSim while emitting comm_dep.")
    ap.add_argument("--G", type=float, default=0.04,
                    help="Inter-node LogGP G, ns/byte.")
    ap.add_argument("--o", type=int, default=200,
                    help="LogGP overhead, ns.")
    ap.add_argument("--g", type=int, default=5,
                    help="LogGOPSim gap, ns.")
    ap.add_argument("--l-intra", type=float, default=350)
    ap.add_argument("--g-intra", type=float, default=None)
    ap.add_argument("--rank-node-map", type=Path, default=None)
    ap.add_argument("--ranks-per-node", type=int, default=None)
    ap.add_argument("--add-barriers", action="store_true")
    ap.add_argument("--nic-per-rank", action="store_true")
    ap.add_argument("--nics-per-node", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned commands and write no generated outputs.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir = args.out_dir.resolve()
    commands: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}

    if args.comm_dep_mode == "existing" and args.comm_dep is None:
        print("error: --comm-dep-mode existing requires --comm-dep", file=sys.stderr)
        return 2
    if args.rank_node_map is not None and args.ranks_per_node is not None:
        print("error: --rank-node-map and --ranks-per-node are mutually exclusive", file=sys.stderr)
        return 2
    if args.ranks_per_node is not None and args.ranks_per_node <= 0:
        print("error: --ranks-per-node must be positive", file=sys.stderr)
        return 2
    if args.nics_per_node <= 0:
        print("error: --nics-per-node must be positive", file=sys.stderr)
        return 2

    if not args.dry_run:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    bin_cache_dir = args.bin_cache_dir.resolve() if args.bin_cache_dir is not None else None

    try:
        if args.sqlite_dir is not None:
            sqlite_dir = args.sqlite_dir.resolve()
            analysis_dir = args.out_dir / "analysis"
            goal = analysis_dir / "output.goal"
            cmd = [
                sys.executable, str(HERE / "run_nccl_generator.py"),
                "--sqlite-dir", str(sqlite_dir),
                "--out-dir", str(analysis_dir),
            ]
            if args.npkit_simple is not None:
                cmd += ["--npkit-simple", str(args.npkit_simple.resolve())]
            if args.npkit_ll is not None:
                cmd += ["--npkit-ll", str(args.npkit_ll.resolve())]
            if args.generator_parallel:
                cmd += ["--parallel"]
            if args.dry_run:
                cmd += ["--dry-run"]
            commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
        else:
            goal = args.goal.resolve()

        if not args.dry_run and not goal.exists():
            raise FileNotFoundError(f"GOAL file not found after generation step: {goal}")
        outputs["goal"] = file_info(goal)

        comm_dep = args.comm_dep.resolve() if args.comm_dep is not None else args.out_dir / "comm_dep.csv"
        mode = args.comm_dep_mode
        if mode == "auto" and args.comm_dep is not None:
            mode = "existing"
        elif mode == "auto":
            mode = "lgs"

        if mode == "existing":
            print(f"[regenerate] using existing comm_dep: {comm_dep}")
        elif mode == "goal":
            cmd = [
                sys.executable, str(HERE / "generate_comm_dep_from_goal.py"),
                "--goal", str(goal),
                "--out", str(comm_dep),
            ]
            commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
        elif mode == "lgs":
            cmd = [
                sys.executable, str(HERE / "run_lgs.py"),
                "--goal", str(goal),
                "--L", str(args.L_sidecar),
                "--G", str(args.G),
                "--o", str(args.o),
                "--g", str(args.g),
                "--comm-dep-out", str(comm_dep),
            ]
            if bin_cache_dir is not None:
                cmd += ["--bin-cache-dir", str(bin_cache_dir)]
            try:
                commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
                if not args.dry_run:
                    validate_comm_dep(comm_dep)
            except Exception:
                if not args.allow_goal_fallback:
                    raise
                print("[regenerate] LogGOPSim sidecar generation failed; "
                      "falling back to GOAL-only matching because "
                      "--allow-goal-fallback was set.")
                cmd = [
                    sys.executable, str(HERE / "generate_comm_dep_from_goal.py"),
                    "--goal", str(goal),
                    "--out", str(comm_dep),
                ]
                commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
        else:
            raise AssertionError(f"unhandled comm_dep mode: {mode}")

        if not args.dry_run:
            outputs["comm_dep"] = validate_comm_dep(comm_dep)
            print(f"[regenerate] comm_dep rows={outputs['comm_dep']['rows']} path={comm_dep}")
        else:
            outputs["comm_dep"] = {"path": str(comm_dep), "dry_run": True}

        if args.lgs_latencies:
            lgs_out = args.out_dir / "lgs_runtime.csv"
            cmd = [
                sys.executable, str(HERE / "run_lgs_sweep.py"),
                "--goal", str(goal),
                "--out", str(lgs_out),
                "--latencies", *(str(x) for x in args.lgs_latencies),
                "--G", str(args.G),
                "--o", str(args.o),
                "--g", str(args.g),
            ]
            if bin_cache_dir is not None:
                cmd += ["--bin-cache-dir", str(bin_cache_dir)]
            commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
            outputs["lgs_runtime"] = file_info(lgs_out)

        lp_common = [
            "--goal", str(goal),
            "--comm-dep", str(comm_dep),
            "--l-intra", fmt_number(args.l_intra),
            "--o", str(args.o),
            "--G", str(args.G),
        ]
        if args.g_intra is not None:
            lp_common += ["--g-intra", str(args.g_intra)]
        if args.rank_node_map is not None:
            lp_common += ["--rank-node-map", str(args.rank_node_map.resolve())]
        if args.ranks_per_node is not None:
            lp_common += ["--ranks-per-node", str(args.ranks_per_node)]
        if args.add_barriers:
            lp_common += ["--add-barriers"]
        if args.nic_per_rank:
            lp_common += ["--nic-per-rank"]
        if args.nics_per_node != 1:
            lp_common += ["--nics-per-node", str(args.nics_per_node)]

        if args.monolithic_latencies:
            points_out = args.out_dir / "monolithic_points.csv"
            cmd = [
                sys.executable, str(HERE / "run_monolithic_points.py"),
                *lp_common,
                "--out", str(points_out),
                "--latencies", *(str(x) for x in args.monolithic_latencies),
            ]
            commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
            outputs["monolithic_points"] = file_info(points_out)

        if args.run_monolithic_sweep:
            sweep_out = args.out_dir / "full_runtime.csv"
            cmd = [
                sys.executable, str(HERE / "run_monolithic_lp.py"),
                *lp_common,
                "--out", str(sweep_out),
                "--l-min", str(args.l_min),
                "--l-max", str(args.l_max),
                "--step", str(args.step),
            ]
            commands.append(run_cmd(cmd, dry_run=args.dry_run, cwd=ROOT))
            outputs["monolithic_sweep"] = file_info(sweep_out)

        manifest = {
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dry_run": args.dry_run,
            "goal_input": str(args.goal.resolve()) if args.goal else None,
            "sqlite_dir_input": str(args.sqlite_dir.resolve()) if args.sqlite_dir else None,
            "out_dir": str(args.out_dir),
            "comm_dep_mode": args.comm_dep_mode,
            "resolved_comm_dep_mode": mode,
            "allow_goal_fallback": args.allow_goal_fallback,
            "bin_cache_dir": str(bin_cache_dir) if bin_cache_dir is not None else None,
            "commands": commands,
            "outputs": outputs,
        }
        if args.dry_run:
            print(json.dumps(manifest, indent=2))
        else:
            manifest_path = args.out_dir / "regeneration_manifest.json"
            with manifest_path.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
                f.write("\n")
            print(f"[regenerate] wrote {manifest_path}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
