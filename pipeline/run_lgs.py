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
import hashlib
import shutil
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LGS_DIR = ROOT / "tools" / "LogGOPSim"
LGS_BIN = LGS_DIR / "LogGOPSim"
TXT2BIN = LGS_DIR / "txt2bin"

FINISH_RE = re.compile(r"Maximum finishing time at host \d+:\s*(\d+)")
HOST_RE = re.compile(r"Host \d+:\s*(\d+)")
TAG_RE = re.compile(r"(?P<prefix>\btag\s+)(?P<tag>\d+)")
MAX_LGS_TAG = (2 ** 32) - 2


def ensure_built() -> None:
    if LGS_BIN.exists() and TXT2BIN.exists():
        return
    print("[lgs] LogGOPSim not built yet; running build_tools.sh")
    r = subprocess.run(["bash", str(HERE / "build_tools.sh")])
    if r.returncode != 0 or not LGS_BIN.exists():
        raise SystemExit("failed to build LogGOPSim")


def goal_needs_tag_normalization(goal_path: Path) -> bool:
    """Return True if any GOAL tag exceeds LogGOPSim's uint32 tag field."""
    with goal_path.open("r", encoding="utf-8") as f:
        for line in f:
            match = TAG_RE.search(line)
            if match and int(match.group("tag")) > MAX_LGS_TAG:
                return True
    return False


def write_tag_normalized_goal(src: Path, dst: Path) -> int:
    """Rewrite GOAL tags to compact uint32-safe IDs while preserving labels."""
    tag_to_id: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        tag = match.group("tag")
        if tag not in tag_to_id:
            tag_to_id[tag] = len(tag_to_id)
            if tag_to_id[tag] > MAX_LGS_TAG:
                raise RuntimeError("too many distinct tags for LogGOPSim uint32 tag field")
        return f"{match.group('prefix')}{tag_to_id[tag]}"

    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for line in fin:
            fout.write(TAG_RE.sub(replace, line))
    return len(tag_to_id)


def bin_cache_path(goal_path: Path, normalize_tags: str, cache_dir: Path) -> Path:
    """Return a local cache path for txt2bin output.

    This intentionally uses metadata instead of hashing full GOAL contents so
    large sweeps avoid rereading multi-GB traces at every latency point.
    """
    st = goal_path.stat()
    raw = "|".join([
        str(goal_path.resolve()),
        str(st.st_size),
        str(st.st_mtime_ns),
        normalize_tags,
    ])
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{key}.bin"


def run_lgs(
    goal_path: Path,
    L: int,
    G: float,
    o: int,
    g: int = 5,
    comm_dep_out: Optional[Path] = None,
    normalize_tags: str = "auto",
    bin_cache_dir: Optional[Path] = None,
) -> int:
    """Run LGS on a GOAL file and return runtime in ns."""
    ensure_built()
    with tempfile.TemporaryDirectory() as tmp:
        if normalize_tags not in {"auto", "always", "never"}:
            raise ValueError("normalize_tags must be one of: auto, always, never")
        tmp_bin = Path(tmp) / "trace.bin"
        cache_path = None
        if bin_cache_dir is not None:
            bin_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = bin_cache_path(goal_path, normalize_tags, bin_cache_dir)
        if cache_path is not None and cache_path.exists():
            shutil.copy2(cache_path, tmp_bin)
            print(f"[lgs] reused txt2bin cache: {cache_path}")
        else:
            lgs_goal = goal_path
            if normalize_tags == "always" or (
                normalize_tags == "auto" and goal_needs_tag_normalization(goal_path)
            ):
                lgs_goal = Path(tmp) / "trace.normalized.goal"
                n_tags = write_tag_normalized_goal(goal_path, lgs_goal)
                print(f"[lgs] normalized {n_tags} distinct GOAL tags for LogGOPSim uint32 compatibility")

            subprocess.run(
                [str(TXT2BIN), "-i", str(lgs_goal), "-o", str(tmp_bin)],
                check=True,
            )
            if cache_path is not None:
                tmp_cache = cache_path.with_suffix(".tmp")
                shutil.copy2(tmp_bin, tmp_cache)
                tmp_cache.replace(cache_path)
                print(f"[lgs] wrote txt2bin cache: {cache_path}")
        cmd = [
            str(LGS_BIN),
            "-f", str(tmp_bin),
            "-L", str(L),
            "-G", str(G),
            "-o", str(o),
            "-g", str(g),
        ]
        if comm_dep_out is not None:
            comm_dep_out.parent.mkdir(parents=True, exist_ok=True)
            cmd += ["--comm-dep-file", str(comm_dep_out)]
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
    ap.add_argument("--comm-dep-out", type=Path, default=None,
                    help="Optional CSV path for patched LogGOPSim send/recv "
                         "dependency output. This file can be passed to "
                         "the LP wrappers as --comm-dep.")
    ap.add_argument("--normalize-tags", choices=("auto", "always", "never"), default="auto",
                    help="Rewrite GOAL tags to compact uint32-safe IDs before "
                         "txt2bin. Default auto only rewrites traces with tags "
                         "larger than LogGOPSim's uint32 tag field.")
    ap.add_argument("--bin-cache-dir", type=Path, default=None,
                    help="Optional local cache directory for txt2bin output.")
    args = ap.parse_args()

    if not args.goal.exists():
        print(f"error: GOAL file not found: {args.goal}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    rt = run_lgs(args.goal, args.L, args.G, args.o, args.g,
                 args.comm_dep_out, args.normalize_tags, args.bin_cache_dir)
    dt = time.perf_counter() - t0
    print(f"[lgs] runtime = {rt} ns ({rt / 1e6:.3f} ms) "
          f"[L={args.L} G={args.G} o={args.o}, solved in {dt:.2f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
