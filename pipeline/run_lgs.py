#!/usr/bin/env python3
"""
Pipeline stage: GOAL trace -> LogGOPSim replay runtime.

Converts the text GOAL to the binary LGS format via ``txt2bin``, then
invokes ``LogGOPSim`` and extracts the last-finishing-rank time.

Usage:
    python3 pipeline/run_lgs.py \\
        --goal data/traces/demo_allreduce_16r_1MiB.goal \\
        --L 1000 --G 0.04 --o 200
"""
import argparse
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LGS_DIR = ROOT / "tools" / "LogGOPSim"
LGS_BIN = LGS_DIR / "LogGOPSim"
TXT2BIN = LGS_DIR / "txt2bin"

FINISH_RE = re.compile(r"Maximum finishing time at host \d+:\s*(\d+)")
HOST_RE = re.compile(r"Host \d+:\s*(\d+)")


def ensure_built() -> None:
    if LGS_BIN.exists() and TXT2BIN.exists():
        return
    print("[lgs] LogGOPSim not built yet; running build_tools.sh")
    r = subprocess.run(["bash", str(HERE / "build_tools.sh")])
    if r.returncode != 0 or not LGS_BIN.exists():
        raise SystemExit("failed to build LogGOPSim")


def run_lgs(goal_path: Path, L: int, G: float, o: int, g: int = 5) -> int:
    """Run LGS on a GOAL file and return runtime in ns."""
    ensure_built()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_bin = Path(tmp) / "trace.bin"
        subprocess.run(
            [str(TXT2BIN), "-i", str(goal_path), "-o", str(tmp_bin)],
            check=True,
        )
        cmd = [
            str(LGS_BIN),
            "-f", str(tmp_bin),
            "-L", str(L),
            "-G", str(G),
            "-o", str(o),
            "-g", str(g),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    m = FINISH_RE.search(r.stdout)
    if m:
        return int(m.group(1))
    hosts = [int(x) for x in HOST_RE.findall(r.stdout)]
    if hosts:
        return max(hosts)
    raise RuntimeError(f"could not parse LGS output:\n{r.stdout}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", required=True, type=Path)
    ap.add_argument("--L", type=int, default=1_000,
                    help="Inter-node latency, ns (default: 1000)")
    ap.add_argument("--G", type=float, default=0.04,
                    help="Inter-node gap per byte, ns/byte (default: 0.04)")
    ap.add_argument("--o", type=int, default=200,
                    help="Overhead, ns (default: 200)")
    ap.add_argument("--g", type=int, default=5,
                    help="Gap, ns (default: 5)")
    args = ap.parse_args()

    if not args.goal.exists():
        print(f"error: GOAL file not found: {args.goal}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    rt = run_lgs(args.goal, args.L, args.G, args.o, args.g)
    dt = time.perf_counter() - t0
    print(f"[lgs] runtime = {rt} ns ({rt / 1e6:.3f} ms) "
          f"[L={args.L} G={args.G} o={args.o}, solved in {dt:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
