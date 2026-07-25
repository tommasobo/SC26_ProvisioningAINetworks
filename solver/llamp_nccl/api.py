"""
High-level API for LLAMP-NCCL analysis.

Provides a single entry point that handles caching, per-collective
solving, and program-level composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cache import CollectiveCache
from .program import ProgramOp, analyze_program, build_program_lp
from .solver import solve_collective
from .types import (
    CollectiveResult,
    CollectiveSignature,
    NetworkParams,
    PiecewiseAffine,
    RingTopology,
)


class LlampNccl:
    """
    Main interface for LLAMP-NCCL latency sensitivity analysis.

    Example:
        llamp = LlampNccl(cache_dir="./llamp_cache")

        # Define network
        net = NetworkParams(G_inter=0.04, G_intra=0.003, L_intra=350, o=200)

        # Define ring topology
        topo = RingTopology.from_dicts(
            n_ranks=8,
            ring_next={0:1, 1:2, 2:3, 3:4, 4:5, 5:6, 6:7, 7:0},
            rank_to_node={r: r // 4 for r in range(8)},
        )

        # Analyze a single collective
        result = llamp.analyze_collective(
            collective_type="allreduce",
            algorithm="ring",
            protocol="simple",
            data_bytes=33554432,
            topo=topo,
            net=net,
        )
        print(f"T(L) has {result.piecewise.n_pieces} pieces")
        print(f"T(0) = {result.piecewise.evaluate(0) / 1e6:.3f} ms")
        print(f"max lambda = {result.piecewise.max_slope}")

        # Analyze a full training iteration
        ops = [
            ProgramOp("compute_fwd", fixed_cost_ns=5_000_000),
            ProgramOp("allreduce_grads", piecewise=result.piecewise),
            ProgramOp("compute_bwd", fixed_cost_ns=8_000_000),
            ProgramOp("allreduce_params", piecewise=result.piecewise),
        ]
        _, program_T = llamp.analyze_program(ops)
        print(f"Program T(0) = {program_T.evaluate(0) / 1e6:.3f} ms")
    """

    def __init__(self, cache_dir: Optional[str | Path] = None):
        self.cache = CollectiveCache(path=cache_dir)

    def analyze_collective(
        self,
        collective_type: str,
        algorithm: str,
        protocol: str,
        data_bytes: int,
        topo: RingTopology,
        net: NetworkParams,
        n_channels: int = 1,
        slice_bytes: int = 1_048_576,
        slices_per_step: int = 2,
        n_outer_loops: Optional[int] = None,
        calc_reduce_ns: float = 13985,
        L_max: float = 1_000_000,
    ) -> CollectiveResult:
        """
        Analyze a single collective. Returns cached result if available.
        """
        if n_outer_loops is None:
            chunk_bytes = slice_bytes * slices_per_step
            channel_work = data_bytes // max(1, n_channels)
            type_size = 4  # float32
            chunk_count = chunk_bytes // type_size
            channel_count = channel_work // type_size
            loop_count = topo.n_ranks * chunk_count
            n_outer_loops = max(1, -(-channel_count // loop_count))

        sig = CollectiveSignature(
            collective_type=collective_type,
            algorithm=algorithm,
            protocol=protocol,
            data_bytes=data_bytes,
            n_ranks=topo.n_ranks,
            n_channels=n_channels,
            slice_bytes=slice_bytes,
            slices_per_step=slices_per_step,
            n_outer_loops=n_outer_loops,
            calc_reduce_ns=calc_reduce_ns,
            ring_topology=topo,
            network=net,
        )

        cached = self.cache.get(sig)
        if cached is not None:
            return cached

        result = solve_collective(sig, L_max)
        self.cache.put(result)
        return result

    def analyze_program(
        self,
        ops: List[ProgramOp],
        L_points: Optional[List[float]] = None,
    ) -> Tuple[object, PiecewiseAffine]:
        """
        Compose per-collective results into a program-level analysis.
        """
        return analyze_program(ops, L_points)

    def cache_summary(self) -> str:
        return self.cache.summary()
