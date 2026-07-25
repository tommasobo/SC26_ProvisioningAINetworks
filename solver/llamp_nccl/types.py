"""
Core data types for LLAMP-NCCL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class RingTopology:
    """Immutable description of a ring's structure."""
    n_ranks: int
    ring_next: Tuple[int, ...]          # ring_next[i] = successor of rank i
    rank_to_node: Tuple[int, ...]       # rank_to_node[i] = node index of rank i

    @staticmethod
    def from_dicts(n_ranks: int,
                   ring_next: Dict[int, int],
                   rank_to_node: Dict[int, int]) -> "RingTopology":
        return RingTopology(
            n_ranks=n_ranks,
            ring_next=tuple(ring_next[r] for r in range(n_ranks)),
            rank_to_node=tuple(rank_to_node[r] for r in range(n_ranks)),
        )

    def prev(self, rank: int) -> int:
        return next(r for r in range(self.n_ranks) if self.ring_next[r] == rank)

    def is_inter_node(self, src: int, dst: int) -> bool:
        return self.rank_to_node[src] != self.rank_to_node[dst]

    @property
    def n_inter_crossings(self) -> int:
        return sum(
            1 for r in range(self.n_ranks)
            if self.is_inter_node(r, self.ring_next[r])
        )


@dataclass(frozen=True)
class NetworkParams:
    """LogGP(S) network parameters."""
    G_inter: float      # ns/byte, inter-node bandwidth
    G_intra: float      # ns/byte, intra-node bandwidth
    L_intra: float      # ns, fixed intra-node latency
    o: float            # ns, per-operation overhead
    msg_gap: float = 0  # ns, per-message NIC gap (LogGPS g parameter)


@dataclass(frozen=True)
class CollectiveSignature:
    """
    Uniquely identifies a collective's LP structure.

    Two collectives with the same signature produce identical T(L)
    functions and can share a cached result.
    """
    collective_type: str            # "allreduce", "allgather", etc.
    algorithm: str                  # "ring", "tree", etc.
    protocol: str                   # "simple", "ll", "ll128"
    data_bytes: int
    n_ranks: int
    n_channels: int
    slice_bytes: int
    slices_per_step: int
    n_outer_loops: int
    calc_reduce_ns: float
    ring_topology: RingTopology
    network: NetworkParams

    def short_description(self) -> str:
        return (
            f"{self.collective_type}_{self.algorithm}_{self.protocol}_"
            f"{self.data_bytes}B_{self.n_ranks}r_{self.n_channels}ch"
        )


@dataclass
class PiecewiseAffine:
    """
    Compact representation of T(L) = max_k (C_k + a_k * L).

    Each piece is (slope, constant): T >= constant + slope * L.
    The pieces are sorted by slope.
    """
    pieces: List[Tuple[float, float]]   # [(slope_0, C_0), (slope_1, C_1), ...]

    @property
    def max_slope(self) -> float:
        return max(a for a, _ in self.pieces) if self.pieces else 0

    @property
    def n_pieces(self) -> int:
        return len(self.pieces)

    def evaluate(self, L: float) -> float:
        """Evaluate T(L) = max_k(C_k + a_k * L)."""
        return max(c + a * L for a, c in self.pieces)

    def sensitivity(self, L: float) -> float:
        """Return the active slope at the given L."""
        best_k = max(range(len(self.pieces)),
                     key=lambda k: self.pieces[k][1] + self.pieces[k][0] * L)
        return self.pieces[best_k][0]

    def breakpoints(self) -> List[Tuple[float, float, float]]:
        """Return (L_transition, slope_before, slope_after) for each transition."""
        if len(self.pieces) < 2:
            return []
        # Sort pieces by slope
        sorted_pieces = sorted(self.pieces, key=lambda p: p[0])
        transitions = []
        for i in range(len(sorted_pieces) - 1):
            a_lo, c_lo = sorted_pieces[i]
            a_hi, c_hi = sorted_pieces[i + 1]
            if a_hi > a_lo:
                L_trans = (c_lo - c_hi) / (a_hi - a_lo)
                if L_trans >= 0:
                    transitions.append((L_trans, a_lo, a_hi))
        return transitions

    def to_dict(self) -> dict:
        return {"pieces": self.pieces}

    @staticmethod
    def from_dict(d: dict) -> "PiecewiseAffine":
        return PiecewiseAffine(pieces=[tuple(p) for p in d["pieces"]])


@dataclass
class CollectiveResult:
    """Full analysis result for one collective."""
    signature: CollectiveSignature
    piecewise: PiecewiseAffine
    lp_vars: int
    lp_constrs: int
    solve_time_s: float
    nic_finish_ns: float = 0  # NIC last-send finish time at L=0
    cpu_finish_ns: float = 0  # CPU last-operation finish time at L=0
