"""
Collective result cache.

Stores piecewise-affine T(L) representations keyed by collective
signature.  Supports JSON persistence for cross-session reuse.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Optional

from .types import CollectiveResult, CollectiveSignature, PiecewiseAffine


def _signature_hash(sig: CollectiveSignature) -> str:
    """Deterministic hash of a signature for cache keys."""
    # Use a stable string representation
    key_parts = [
        sig.collective_type,
        sig.algorithm,
        sig.protocol,
        str(sig.data_bytes),
        str(sig.n_ranks),
        str(sig.n_channels),
        str(sig.slice_bytes),
        str(sig.slices_per_step),
        str(sig.n_outer_loops),
        f"{sig.calc_reduce_ns:.2f}",
        str(sig.ring_topology.ring_next),
        str(sig.ring_topology.rank_to_node),
        f"{sig.network.G_inter:.6f}",
        f"{sig.network.G_intra:.6f}",
        f"{sig.network.L_intra:.2f}",
        f"{sig.network.o:.2f}",
        f"{sig.network.msg_gap:.2f}",
    ]
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class CollectiveCache:
    """
    In-memory + optional disk cache for collective analysis results.

    Usage:
        cache = CollectiveCache(path="./llamp_cache")
        result = cache.get(signature)
        if result is None:
            result = solve_collective(signature)
            cache.put(result)
    """

    def __init__(self, path: Optional[Path | str] = None):
        self._memory: Dict[str, CollectiveResult] = {}
        self._disk_path: Optional[Path] = Path(path) if path else None
        if self._disk_path:
            self._disk_path.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def get(self, sig: CollectiveSignature) -> Optional[CollectiveResult]:
        key = _signature_hash(sig)
        return self._memory.get(key)

    def put(self, result: CollectiveResult) -> None:
        key = _signature_hash(result.signature)
        self._memory[key] = result
        if self._disk_path:
            self._save_entry(key, result)

    def has(self, sig: CollectiveSignature) -> bool:
        return _signature_hash(sig) in self._memory

    @property
    def size(self) -> int:
        return len(self._memory)

    def summary(self) -> str:
        lines = [f"CollectiveCache: {self.size} entries"]
        for key, result in self._memory.items():
            pw = result.piecewise
            desc = result.signature.short_description() if result.signature else key
            lines.append(
                f"  [{key}] {desc} "
                f"→ {pw.n_pieces} pieces, max_λ={pw.max_slope:.0f}, "
                f"solved in {result.solve_time_s:.2f}s"
            )
        return "\n".join(lines)

    def _save_entry(self, key: str, result: CollectiveResult) -> None:
        entry = {
            "key": key,
            "description": result.signature.short_description(),
            "piecewise": result.piecewise.to_dict(),
            "lp_vars": result.lp_vars,
            "lp_constrs": result.lp_constrs,
            "solve_time_s": result.solve_time_s,
            "nic_finish_ns": result.nic_finish_ns,
            "cpu_finish_ns": result.cpu_finish_ns,
        }
        path = self._disk_path / f"{key}.json"
        path.write_text(json.dumps(entry, indent=2))

    def _load_from_disk(self) -> None:
        """Load cached piecewise results from disk.

        Note: only the piecewise representation is restored.  The full
        CollectiveSignature is not stored on disk — the cache acts as a
        warm-start hint for known hashes.
        """
        if not self._disk_path:
            return
        for path in self._disk_path.glob("*.json"):
            try:
                entry = json.loads(path.read_text())
                pw = PiecewiseAffine.from_dict(entry["piecewise"])
                # Store a lightweight result without the full signature
                self._memory[entry["key"]] = CollectiveResult(
                    signature=None,  # type: ignore  — restored from hash only
                    piecewise=pw,
                    lp_vars=entry.get("lp_vars", 0),
                    lp_constrs=entry.get("lp_constrs", 0),
                    solve_time_s=entry.get("solve_time_s", 0),
                    nic_finish_ns=entry.get("nic_finish_ns", 0),
                    cpu_finish_ns=entry.get("cpu_finish_ns", 0),
                )
            except (json.JSONDecodeError, KeyError):
                continue
