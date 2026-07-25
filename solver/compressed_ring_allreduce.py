"""
Compressed LP formulations for NCCL Ring AllReduce.

Approach 2 — Macro-vertex LP:
    Two variables per step per rank.  Cross-rank constraints capture
    only the network delay (L + BW + o).  Local processing is captured
    separately via the sequential constraint chain.

Approach 3 — Pipeline LP:
    T = max(T_nic, T_fill + T_ring_latency_one_pass).
    The ring latency covers a single pass (both phases of one outer loop),
    not all outer loops, because the pipeline fill already accounts
    for the sequential injection of all data.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import gurobipy as gp


@dataclass
class RingAllReduceParams:
    """All parameters needed to describe a ring allreduce collective."""
    n_ranks: int
    data_bytes: int
    slice_bytes: int
    slices_per_step: int
    n_channels: int
    ring_next: Dict[int, int]
    rank_to_node: Dict[int, int]
    G_inter: float
    G_intra: float
    L_intra: float
    o: float
    calc_reduce_ns: float
    n_outer_loops: int

    @property
    def ring_prev(self) -> Dict[int, int]:
        return {v: k for k, v in self.ring_next.items()}

    def is_inter_node(self, src: int, dst: int) -> bool:
        return self.rank_to_node[src] != self.rank_to_node[dst]

    def G_for_send(self, src: int) -> float:
        return (self.G_inter if self.is_inter_node(src, self.ring_next[src])
                else self.G_intra)

    def G_for_recv(self, dst: int) -> float:
        return (self.G_inter if self.is_inter_node(self.ring_prev[dst], dst)
                else self.G_intra)

    @property
    def n_steps_per_phase(self) -> int:
        return self.n_ranks - 1

    @property
    def n_phases(self) -> int:
        return 2

    @property
    def total_steps_per_rank(self) -> int:
        return self.n_outer_loops * self.n_phases * self.n_steps_per_phase

    def ring_order(self) -> List[int]:
        ring = []
        r = 0
        for _ in range(self.n_ranks):
            ring.append(r)
            r = self.ring_next[r]
        return ring


# =========================================================================
# Approach 2: Macro-vertex LP
# =========================================================================

def build_macro_vertex_lp(p: RingAllReduceParams) -> gp.Model:
    """
    Two variables per (rank, step):
        send_start[r,k] — when the NIC starts injecting this step's sends
        step_end[r,k]   — when this step's local processing completes

    Three constraint families:
        NIC serial:  send_start[r,k] >= send_start[r,k-1] + inject_time
        Sequential:  send_start[r,k] >= step_end[r,k-1]
        Cross-rank:  send_start[r,k] >= send_start[prev_r, k-1] + L + BW + o
                     (network delay only — local processing is in step_end)
    """
    model = gp.Model("RingAR_MacroVertex")
    model.setParam("LogToConsole", 0)

    l = model.addVar(name="l")
    n_steps = p.total_steps_per_rank
    S = p.slices_per_step
    prev_rank = p.ring_prev

    send_start = {}
    step_end = {}
    for r in range(p.n_ranks):
        for k in range(n_steps):
            send_start[r, k] = model.addVar(name=f"ss_{r}_{k}")
            step_end[r, k] = model.addVar(name=f"se_{r}_{k}")
    model.update()

    for r in range(p.n_ranks):
        is_inter_recv = p.is_inter_node(prev_rank[r], r)
        inject_per_step = S * p.slice_bytes * p.G_for_send(r)
        recv_bw = p.slice_bytes * p.G_for_recv(r)
        l_recv = l if is_inter_recv else p.L_intra

        for k in range(n_steps):
            phase_offset = k % (p.n_phases * p.n_steps_per_phase)
            is_rs = phase_offset < p.n_steps_per_phase
            phase_step = phase_offset % p.n_steps_per_phase
            is_first_step = (phase_step == 0)
            has_reduce = is_rs and not is_first_step

            # Local processing cost for this step
            if is_first_step:
                local_cost = S * p.o  # send-only
            else:
                calc = p.calc_reduce_ns if has_reduce else 0
                local_cost = S * (p.o + calc + p.o)  # recv_o + calc + send_o

            # NIC serialization
            if k > 0:
                model.addConstr(
                    send_start[r, k] >= send_start[r, k - 1] + inject_per_step,
                    name=f"nic_{r}_{k}"
                )

            # Sequential kernel execution
            if k > 0:
                model.addConstr(
                    send_start[r, k] >= step_end[r, k - 1],
                    name=f"seq_{r}_{k}"
                )

            # Cross-rank dependency (network delay only)
            # The recv needs the previous rank's send data to arrive.
            # Cost: L + BW + o (the receiver's overhead to receive the data)
            if not is_first_step and k > 0:
                model.addConstr(
                    send_start[r, k] >= send_start[prev_rank[r], k - 1]
                        + l_recv + recv_bw + p.o,
                    name=f"xrank_{r}_{k}"
                )

            # Step completion
            model.addConstr(
                step_end[r, k] >= send_start[r, k] + local_cost,
                name=f"end_{r}_{k}"
            )

            if k == 0:
                model.addConstr(send_start[r, k] >= 0, name=f"init_{r}")

    # Objective: last step's NIC injection must complete
    t = model.addVar(name="t")
    for r in range(p.n_ranks):
        last_inject = S * p.slice_bytes * p.G_for_send(r)
        model.addConstr(
            t >= send_start[r, n_steps - 1] + last_inject + S * p.o,
            name=f"obj_{r}"
        )
    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()
    return model


# =========================================================================
# Approach 3: Pipeline LP
# =========================================================================

def build_pipeline_lp(p: RingAllReduceParams) -> gp.Model:
    """
    Pipeline model:  T = max(T_nic, T_fill + T_drain)

    T_nic   = total_slices * inject_time   (NIC pipeline, constant in L)
    T_fill  = (total_slices - 1) * inject_time  (pipeline startup)
    T_drain = latency for one chunk to traverse the ring (one full pass)
              = sum over N-1 hops per phase of (L or L_intra + o + calc)
              BW is NOT included because the pipeline fill already covers it.

    The drain covers both phases (RS + AG) of ONE outer loop iteration.
    Multiple outer loops don't multiply the drain because the pipeline
    fill covers the sequential injection across outer loops.
    """
    model = gp.Model("RingAR_Pipeline")
    model.setParam("LogToConsole", 0)

    l = model.addVar(name="l")
    t = model.addVar(name="t")

    N = p.n_ranks
    S = p.slices_per_step
    ring = p.ring_order()
    n_steps = p.n_steps_per_phase

    total_slices = p.total_steps_per_rank * S
    max_inject = max(p.slice_bytes * p.G_for_send(r) for r in range(N))

    # NIC pipeline bound (constant)
    T_nic = total_slices * max_inject
    model.addConstr(t >= T_nic, name="nic_bound")

    # Pipeline fill: all slices except the last one
    T_fill = (total_slices - 1) * max_inject

    # Drain: last chunk traverses the ring (one outer loop = RS + AG)
    # Only latency, overhead, and compute — no BW (covered by fill).
    drain = 0.0
    for phase_idx in range(p.n_phases):
        is_rs = (phase_idx == 0)
        for step in range(n_steps):
            src = ring[step]
            dst = ring[(step + 1) % N]
            is_inter = p.is_inter_node(src, dst)

            l_hop = l if is_inter else p.L_intra
            hop_cost = l_hop + p.o
            if is_rs and step > 0:
                hop_cost = hop_cost + p.calc_reduce_ns

            drain = drain + hop_cost

    model.addConstr(t >= T_fill + drain, name="pipeline_bound")

    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()
    return model


# =========================================================================
# Utilities
# =========================================================================

def sweep_model(model: gp.Model, L_points: List[int]) -> Tuple[List[float], List[float]]:
    l_var = model.getVarByName("l")
    runtimes, sensitivities = [], []
    for L in L_points:
        l_var.lb = L
        model.optimize()
        assert model.status == gp.GRB.OPTIMAL, f"LP infeasible at L={L}"
        runtimes.append(model.objVal)
        sensitivities.append(l_var.RC)
    return runtimes, sensitivities


def get_model_size(model: gp.Model) -> Tuple[int, int]:
    return model.NumVars, model.NumConstrs
