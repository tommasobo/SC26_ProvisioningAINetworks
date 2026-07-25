"""
Program-level latency sensitivity analysis.

Composes per-collective piecewise-affine T(L) representations into a
full-program LP that captures inter-collective dependencies (compute
gaps, sequential ordering).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import gurobipy as gp

from .types import PiecewiseAffine


@dataclass
class ProgramOp:
    """One operation in the program's execution timeline."""
    name: str
    piecewise: Optional[PiecewiseAffine] = None  # None for compute ops
    fixed_cost_ns: float = 0                      # for compute ops
    nic_finish_ns: float = 0  # NIC last-send finish at L=0 (for NIC-gap overlap)
    cpu_finish_ns: float = 0  # CPU last-op finish at L=0


def build_program_lp(ops: List[ProgramOp]) -> gp.Model:
    """
    Build a program-level LP from a sequence of operations.

    Each operation is either:
    - A collective (has a PiecewiseAffine T(L) representation)
    - A compute phase (has a fixed cost, independent of L)

    Operations execute sequentially: op[i+1] starts after op[i] finishes.
    The LP finds T_program(L) = total runtime as a function of L.

    For each collective op with pieces [(a_0, C_0), (a_1, C_1), ...]:
        finish[i] >= start[i] + C_k + a_k * L   for each piece k
        start[i+1] >= finish[i]

    For each compute op:
        finish[i] = start[i] + fixed_cost

    Variables: L, start[i] for each op, T (total runtime).
    Constraints: O(sum of n_pieces across collectives).
    """
    model = gp.Model("Program")
    model.setParam("LogToConsole", 0)

    l = model.addVar(name="l")
    t = model.addVar(name="t")

    starts = []
    finishes = []
    for i, op in enumerate(ops):
        s = model.addVar(name=f"s_{i}")
        f = model.addVar(name=f"f_{i}")
        starts.append(s)
        finishes.append(f)
    model.update()

    for i, op in enumerate(ops):
        # Sequential ordering
        if i == 0:
            model.addConstr(starts[i] >= 0, name=f"start_{i}")
        else:
            model.addConstr(starts[i] >= finishes[i - 1], name=f"seq_{i}")

        if op.piecewise is not None:
            # Collective: finish >= start + T_collective(L)
            for k, (slope, constant) in enumerate(op.piecewise.pieces):
                model.addConstr(
                    finishes[i] >= starts[i] + constant + slope * l,
                    name=f"piece_{i}_{k}",
                )
        else:
            # Compute: finish = start + fixed_cost
            model.addConstr(
                finishes[i] >= starts[i] + op.fixed_cost_ns,
                name=f"compute_{i}",
            )

    # Objective
    model.addConstr(t >= finishes[-1], name="obj")
    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()
    return model


def analyze_program(
    ops: List[ProgramOp],
    L_points: Optional[List[float]] = None,
) -> Tuple[gp.Model, PiecewiseAffine]:
    """
    Build and solve the program LP, extract program-level T(L).

    Returns the model and the program's piecewise-affine T(L).
    """
    if L_points is None:
        L_points = list(range(0, 1_000_001, 10_000))

    model = build_program_lp(ops)
    l_var = model.getVarByName("l")

    # Sweep to find breakpoints
    pieces_dict: dict[float, float] = {}
    for L in L_points:
        l_var.lb = L
        model.optimize()
        slope = round(l_var.RC, 2)
        T = model.objVal
        C = T - slope * L
        if slope not in pieces_dict or C > pieces_dict[slope]:
            pieces_dict[slope] = C

    pieces = sorted(pieces_dict.items(), key=lambda p: p[0])
    return model, PiecewiseAffine(pieces=pieces)


def analyze_parallel_streams(
    stream_ops: Dict[str, List[ProgramOp]],
    L_points: Optional[List[float]] = None,
) -> Tuple[gp.Model, PiecewiseAffine]:
    """
    Compose multiple independent streams in parallel (fork-join),
    with NIC-gap overlap modeling.

    Each stream has two parallel paths:
      - CPU path: sequential with gaps (gap blocks CPU operations)
      - NIC path: sequential without gaps (NIC transitions between
        collectives immediately, no gap delay)

    The finish time of each collective is max(CPU_path, NIC_path).
    This captures the monolithic LP's behavior where gap calc vertices
    only block the CPU, not the NIC injection chain.
    """
    if L_points is None:
        L_points = list(range(0, 1_000_001, 10_000))

    model = gp.Model("ParallelStreams")
    model.setParam("LogToConsole", 0)

    l = model.addVar(name="l")
    t = model.addVar(name="t")
    model.update()

    for stream_name, ops in stream_ops.items():
        if not ops:
            continue

        # Check if any ops have meaningful NIC/CPU decomposition.
        # The NIC-gap overlap model only helps when rank 0's NIC finishes
        # well before its CPU (i.e., there's significant cross-collective
        # NIC pipeline room). If nic_finish ≈ cpu_finish, the overlap
        # is negligible and the simpler sequential model is more accurate.
        # Threshold: NIC must finish at least 10% earlier than CPU.
        def _has_meaningful_nic(op):
            if op.piecewise is None or op.nic_finish_ns <= 0 or op.cpu_finish_ns <= 0:
                return False
            lag_frac = (op.cpu_finish_ns - op.nic_finish_ns) / op.cpu_finish_ns
            return lag_frac > 0.10
        has_nic_info = any(_has_meaningful_nic(op) for op in ops)

        if has_nic_info:
            # Model with NIC-gap overlap
            cpu_starts, cpu_finishes = [], []
            nic_finishes = []
            finishes = []  # actual finish = max(cpu, nic)

            for i, op in enumerate(ops):
                cs = model.addVar(name=f"cs_{stream_name}_{i}")
                cf = model.addVar(name=f"cf_{stream_name}_{i}")
                nf = model.addVar(name=f"nf_{stream_name}_{i}")
                f = model.addVar(name=f"f_{stream_name}_{i}")
                cpu_starts.append(cs); cpu_finishes.append(cf)
                nic_finishes.append(nf); finishes.append(f)
            model.update()

            for i, op in enumerate(ops):
                if i == 0:
                    model.addConstr(cpu_starts[i] >= 0)
                else:
                    # CPU path: must wait for previous op to finish
                    model.addConstr(cpu_starts[i] >= finishes[i - 1])

                if op.piecewise is not None:
                    # Collective op
                    # CPU finish: start + T_collective(L)
                    for k, (slope, constant) in enumerate(op.piecewise.pieces):
                        model.addConstr(cpu_finishes[i] >= cpu_starts[i] + constant + slope * l)

                    # NIC finish: the NIC chain skips gaps entirely.
                    # The NIC contribution per collective = T(L) - cpu_nic_lag
                    # where cpu_nic_lag = cpu_finish_ns - nic_finish_ns at L=0.
                    # This ensures the NIC path grows with L (same slope as T(L)).
                    if op.nic_finish_ns > 0:
                        cpu_nic_lag = max(0, op.cpu_finish_ns - op.nic_finish_ns)

                        # Find previous collective's NIC finish
                        prev_nic = None
                        for j in range(i - 1, -1, -1):
                            if ops[j].piecewise is not None and ops[j].nic_finish_ns > 0:
                                prev_nic = j; break

                        # NIC path: prev_nic_finish + (T_collective(L) - cpu_nic_lag)
                        # = prev_nic_finish + C_k + slope_k * L - cpu_nic_lag
                        for k, (slope, constant) in enumerate(op.piecewise.pieces):
                            nic_cost = constant - cpu_nic_lag  # may be negative → clamped by max with 0
                            if prev_nic is not None:
                                model.addConstr(nic_finishes[i] >= nic_finishes[prev_nic] + nic_cost + slope * l)
                            else:
                                model.addConstr(nic_finishes[i] >= nic_cost + slope * l)

                        # Actual finish = max(cpu_finish, nic_finish)
                        model.addConstr(finishes[i] >= cpu_finishes[i])
                        model.addConstr(finishes[i] >= nic_finishes[i])
                    else:
                        # No NIC info: treat as CPU-only
                        model.addConstr(nic_finishes[i] >= 0)
                        model.addConstr(finishes[i] >= cpu_finishes[i])
                else:
                    # Gap or compute op: only affects CPU path
                    model.addConstr(cpu_finishes[i] >= cpu_starts[i] + op.fixed_cost_ns)
                    # NIC is unaffected by gaps — carry forward previous NIC finish
                    if i > 0:
                        model.addConstr(nic_finishes[i] >= nic_finishes[i - 1])
                    else:
                        model.addConstr(nic_finishes[i] >= 0)
                    model.addConstr(finishes[i] >= cpu_finishes[i])

            model.addConstr(t >= finishes[-1])
        else:
            # No NIC info: original sequential model
            starts, finishes = [], []
            for i, op in enumerate(ops):
                s = model.addVar(name=f"s_{stream_name}_{i}")
                f = model.addVar(name=f"f_{stream_name}_{i}")
                starts.append(s); finishes.append(f)
            model.update()

            for i, op in enumerate(ops):
                if i == 0:
                    model.addConstr(starts[i] >= 0)
                else:
                    model.addConstr(starts[i] >= finishes[i - 1])

                if op.piecewise is not None:
                    for k, (slope, constant) in enumerate(op.piecewise.pieces):
                        model.addConstr(finishes[i] >= starts[i] + constant + slope * l)
                else:
                    model.addConstr(finishes[i] >= starts[i] + op.fixed_cost_ns)

            model.addConstr(t >= finishes[-1])

    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()

    # Sweep
    pieces_dict: dict[float, float] = {}
    for L in L_points:
        l.lb = L
        model.optimize()
        slope = round(l.RC, 2)
        T = model.objVal
        C = T - slope * L
        if slope not in pieces_dict or C > pieces_dict[slope]:
            pieces_dict[slope] = C

    pieces = sorted(pieces_dict.items(), key=lambda p: p[0])
    return model, PiecewiseAffine(pieces=pieces)
