#!/usr/bin/env python3
"""Generate an LP comm_dep.csv sidecar by FIFO matching send/recv operations.

The solver consumes a four-column sidecar:

    src_rank,src_label_offset,dst_rank,dst_label_offset

Patched LogGOPSim can emit the same file while replaying a GOAL trace, but
some traces exercise LogGOPSim parser limitations. This fallback performs the
message matching directly on the text GOAL. By default it matches FIFO by
``(src_rank, dst_rank, tag)`` and intentionally ignores CPU/NIC, matching the
LogGOPSim queue key. Use ``--include-cpu`` only for traces known to require it.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict, deque
from pathlib import Path


RANK_RE = re.compile(r"^rank\s+(\d+)\s+{$")
LABEL_DEF_RE = re.compile(r"^l(?P<label>\d+)\s*:")
SEND_RE = re.compile(
    r"^l(?P<label>\d+)\s*:\s*send\s+(?P<size>\d+)b\s+to\s+(?P<peer>\d+)"
    r"(?:\s+tag\s+(?P<tag>\d+))?(?:\s*cpu\s+(?P<cpu>\d+))?(?:\s*nic\s+(?P<nic>\d+))?$"
)
RECV_RE = re.compile(
    r"^l(?P<label>\d+)\s*:\s*recv\s+(?P<size>\d+)b\s+from\s+(?P<peer>\d+)"
    r"(?:\s+tag\s+(?P<tag>\d+))?(?:\s*cpu\s+(?P<cpu>\d+))?(?:\s*nic\s+(?P<nic>\d+))?$"
)


def _key(src: int, dst: int, tag: str, cpu: str | None, include_cpu: bool) -> tuple:
    return (src, dst, tag, cpu or "0") if include_cpu else (src, dst, tag)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--goal", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--include-cpu", action="store_true",
                    help="Include CPU in the match key. Default matches "
                         "LogGOPSim's receive queue behavior and ignores CPU.")
    ap.add_argument("--allow-unmatched", action="store_true",
                    help="Write matched pairs even if unmatched sends/recvs remain.")
    args = ap.parse_args()

    if not args.goal.exists():
        print(f"error: GOAL file not found: {args.goal}", file=sys.stderr)
        return 2

    pending_sends: dict[tuple, deque[tuple[int, int]]] = defaultdict(deque)
    pending_recvs: dict[tuple, deque[tuple[int, int]]] = defaultdict(deque)
    matches: list[tuple[int, int, int, int]] = []
    curr_rank: int | None = None
    min_label: int | None = None
    n_send = 0
    n_recv = 0

    with args.goal.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            rank_match = RANK_RE.match(line)
            if rank_match:
                curr_rank = int(rank_match.group(1))
                continue
            if line == "}":
                curr_rank = None
                continue
            if curr_rank is None:
                continue
            label_match = LABEL_DEF_RE.match(line)
            if label_match:
                label = int(label_match.group("label"))
                min_label = label if min_label is None else min(min_label, label)

            send_match = SEND_RE.match(line)
            if send_match:
                label = int(send_match.group("label"))
                dst = int(send_match.group("peer"))
                tag = send_match.group("tag") or "0"
                key = _key(curr_rank, dst, tag, send_match.group("cpu"), args.include_cpu)
                n_send += 1
                if pending_recvs[key]:
                    recv_rank, recv_label = pending_recvs[key].popleft()
                    matches.append((curr_rank, label, recv_rank, recv_label))
                else:
                    pending_sends[key].append((curr_rank, label))
                continue

            recv_match = RECV_RE.match(line)
            if recv_match:
                label = int(recv_match.group("label"))
                src = int(recv_match.group("peer"))
                tag = recv_match.group("tag") or "0"
                key = _key(src, curr_rank, tag, recv_match.group("cpu"), args.include_cpu)
                n_recv += 1
                if pending_sends[key]:
                    send_rank, send_label = pending_sends[key].popleft()
                    matches.append((send_rank, send_label, curr_rank, label))
                else:
                    pending_recvs[key].append((curr_rank, label))
                continue

    unmatched_sends = sum(len(v) for v in pending_sends.values())
    unmatched_recvs = sum(len(v) for v in pending_recvs.values())
    if (unmatched_sends or unmatched_recvs) and not args.allow_unmatched:
        print(
            "error: unmatched operations while generating comm_dep: "
            f"{unmatched_sends} sends, {unmatched_recvs} recvs. "
            "Use --allow-unmatched only for diagnostics.",
            file=sys.stderr,
        )
        for name, pending in (("send", pending_sends), ("recv", pending_recvs)):
            shown = 0
            for key, queue in pending.items():
                for rank, label in queue:
                    print(f"  unmatched {name}: rank={rank} label=l{label} key={key}", file=sys.stderr)
                    shown += 1
                    if shown >= 10:
                        break
                if shown >= 10:
                    break
        return 1

    label_offset = 1 if min_label is not None and min_label >= 1 else 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for src_rank, src_label, dst_rank, dst_label in matches:
            out.write(
                f"{src_rank},{src_label - label_offset},"
                f"{dst_rank},{dst_label - label_offset}\n"
            )

    print(
        f"[comm-dep] wrote {args.out}: {len(matches)} matches "
        f"from {n_send} sends and {n_recv} recvs "
        f"(label_offset={label_offset}, include_cpu={args.include_cpu})"
    )
    if unmatched_sends or unmatched_recvs:
        print(f"[comm-dep] warning: left unmatched sends={unmatched_sends}, recvs={unmatched_recvs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
