"""
Per-collective LP solver.

Builds and solves the full slice-level LP for a single collective,
then extracts the piecewise-affine T(L) representation using LLAMP's
reduced-cost algorithm.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

import gurobipy as gp

from .types import (
    CollectiveResult,
    CollectiveSignature,
    NetworkParams,
    PiecewiseAffine,
    RingTopology,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepend_sys_path(path: Path) -> None:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _resolve_generator_dir() -> Path:
    env = os.environ.get("LLAMP_NCCL_GENERATOR_DIR")
    candidates = []
    if env:
        candidates.append(Path(env))
    root = _repo_root()
    candidates.extend([
        root / "tools" / "nccl_generator",
        root / "tools" / "nccl_generator_v2_hwfix",
    ])
    for candidate in candidates:
        if (candidate / "nccl_comm.py").exists() and (candidate / "goal.py").exists():
            return candidate
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "Could not locate the NCCL generator Python modules. "
        "Set LLAMP_NCCL_GENERATOR_DIR or install tools/nccl_generator. "
        f"Tried: {tried}"
    )


def _resolve_npkit_paths() -> tuple[Path, Path]:
    root = _repo_root()
    simple_env = os.environ.get("LLAMP_NPKIT_SIMPLE")
    ll_env = os.environ.get("LLAMP_NPKIT_LL")
    simple = Path(simple_env) if simple_env else root / "data" / "npkit" / "npkit_alps_simple.json"
    ll = Path(ll_env) if ll_env else root / "data" / "npkit" / "npkit_alps_ll.json"
    if simple.exists() and ll.exists():
        return simple, ll

    legacy_root = root / "workspaces" / "collective_motif_clean_20260329" / "reference_bundle" / "npkit_results"
    legacy_simple = legacy_root / "simple_1ch" / "npkit_data_summary_Simple_alps.json"
    legacy_ll = legacy_root / "ll_1ch" / "npkit_data_summary_LL_alps.json"
    if legacy_simple.exists() and legacy_ll.exists():
        return legacy_simple, legacy_ll

    raise FileNotFoundError(
        "Could not locate NPKit timing summaries for Composite-LP motif generation. "
        "Set LLAMP_NPKIT_SIMPLE and LLAMP_NPKIT_LL, or provide data/npkit/npkit_alps_simple.json "
        "and data/npkit/npkit_alps_ll.json."
    )


def build_ring_allreduce_lp(sig: CollectiveSignature) -> gp.Model:
    """
    Build the full slice-level LP for a ring allreduce from its signature.

    Uses the GOAL-file approach: parallel steps with NIC serialization
    in topological (interleaved) order + intra/inter-node distinction.
    """
    topo = sig.ring_topology
    net = sig.network
    N = sig.n_ranks
    S = sig.slices_per_step
    n_spp = N - 1           # steps per phase
    n_ph = 2                # reduce-scatter + allgather
    n_ol = sig.n_outer_loops
    total_steps = n_ol * n_ph * n_spp
    total_slices = total_steps * S

    model = gp.Model(sig.short_description())
    model.setParam("LogToConsole", 0)
    l = model.addVar(name="l")

    # One variable per (rank, NIC_slot). Slots follow interleaved order.
    ss = {}
    for r in range(N):
        for i in range(total_slices):
            ss[r, i] = model.addVar(name=f"s_{r}_{i}")
    model.update()

    # Build the interleaved slot ordering.
    # Pattern: for each step position within an outer loop,
    #          interleave all outer loops, then advance to next step.
    steps_per_ol = n_ph * n_spp
    interleaved = []
    for step_in_ol in range(steps_per_ol):
        for ol in range(n_ol):
            for s in range(S):
                phase = 0 if step_in_ol < n_spp else 1
                phase_step = step_in_ol % n_spp
                interleaved.append((ol, phase, phase_step, s))

    # Build a reverse lookup: (ol, phase, phase_step, slice) -> NIC slot index
    slot_of = {entry: i for i, entry in enumerate(interleaved)}

    for r in range(N):
        prev_r = topo.prev(r)
        is_inter_recv = topo.is_inter_node(prev_r, r)
        is_inter_send = topo.is_inter_node(r, topo.ring_next[r])
        inject = sig.slice_bytes * (net.G_inter if is_inter_send else net.G_intra)
        recv_bw = sig.slice_bytes * (net.G_inter if is_inter_recv else net.G_intra)
        l_recv = l if is_inter_recv else net.L_intra

        for i in range(total_slices):
            ol, ph, ps, s = interleaved[i]
            is_first = (ps == 0)
            is_rs = (ph == 0)
            has_reduce = is_rs and not is_first

            # NIC serialization (linear chain in interleaved order)
            if i > 0:
                model.addConstr(ss[r, i] >= ss[r, i - 1] + inject,
                                name=f"nic_{r}_{i}")
            else:
                model.addConstr(ss[r, i] >= 0, name=f"init_{r}")

            # Cross-rank dependency
            if not is_first:
                prev_entry = (ol, ph, ps - 1, s)
                prev_i = slot_of[prev_entry]
                calc = sig.calc_reduce_ns if has_reduce else 0
                model.addConstr(
                    ss[r, i] >= ss[prev_r, prev_i] + l_recv + recv_bw + 2 * net.o + calc,
                    name=f"xr_{r}_{i}",
                )

    # Objective: last NIC slot must finish injecting + overhead
    t = model.addVar(name="t")
    for r in range(N):
        is_inter_send = topo.is_inter_node(r, topo.ring_next[r])
        inject = sig.slice_bytes * (net.G_inter if is_inter_send else net.G_intra)
        model.addConstr(t >= ss[r, total_slices - 1] + inject + net.o,
                        name=f"obj_{r}")
    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()
    return model


def extract_piecewise(model: gp.Model,
                      L_max: float = 1_000_000) -> PiecewiseAffine:
    """
    Extract the piecewise-affine T(L) by sweeping L and detecting
    slope changes via the reduced cost of the l variable.
    """
    l_var = model.getVarByName("l")
    pieces: list[tuple[float, float]] = []
    prev_slope: Optional[float] = None

    # Binary-search style: start at L_max, find slope, then step down
    # to find where it changes.  Simple sweep is fine for small n_pieces.
    l_var.lb = L_max
    model.optimize()
    max_slope = l_var.RC
    T_max = model.objVal
    C_max = T_max - max_slope * L_max
    pieces.append((max_slope, C_max))

    # Walk backward using SALBLow-style: at current L, the basis is optimal
    # down to SALBLow(l). Use Gurobi's variable SALBLow attribute.
    L_current = L_max
    while L_current > 0:
        l_var.lb = L_current
        model.optimize()
        slope = l_var.RC
        T_val = model.objVal
        C_val = T_val - slope * L_current

        if prev_slope is None or abs(slope - prev_slope) > 0.01:
            pieces.append((slope, C_val))
            prev_slope = slope

        # Find how far left this basis is valid
        try:
            lb_low = l_var.SAObjLow  # Gurobi sensitivity: smallest obj at this basis
            # SAObjLow gives the objective lower bound, not L.
            # Use: at basis change, C_current + slope*L = C_next + slope_next*L
            # We need the L where the next piece takes over.
            # Simplest: step by a fixed amount and re-solve.
            L_current -= max(1, L_current * 0.01)
            if L_current < 0:
                L_current = 0
        except AttributeError:
            L_current -= 1000
            if L_current < 0:
                L_current = 0

    # Also solve at L=0
    l_var.lb = 0
    model.optimize()
    slope_0 = l_var.RC
    T_0 = model.objVal
    C_0 = T_0 - slope_0 * 0
    pieces.append((slope_0, C_0))

    # Deduplicate and keep only the tightest per slope
    slope_to_C: dict[float, float] = {}
    for slope, C in pieces:
        s_round = round(slope, 2)
        if s_round not in slope_to_C or C > slope_to_C[s_round]:
            slope_to_C[s_round] = C

    final_pieces = sorted(slope_to_C.items(), key=lambda p: p[0])
    return PiecewiseAffine(pieces=final_pieces)


def build_ring_allgather_lp(sig: CollectiveSignature) -> gp.Model:
    """
    Build the full slice-level LP for a ring allgather.

    Uses separate send and recv variables per NIC slot, matching the
    monolithic LP's formulation.  The send variable tracks NIC injection
    time (chained through the NIC).  The recv variable tracks data
    arrival from the previous rank.  A send can inject into the NIC
    before the recv for the same slot completes, enabling pipelining
    between recv-wait and NIC injection of the next chunk.
    """
    topo = sig.ring_topology
    net = sig.network
    N = sig.n_ranks
    S = sig.slices_per_step
    n_spp = N - 1
    n_ol = sig.n_outer_loops
    total_steps = n_ol * n_spp
    total_slices = total_steps * S

    model = gp.Model(sig.short_description())
    model.setParam("LogToConsole", 0)
    l = model.addVar(name="l")

    # Separate send (NIC injection) and recv variables per slot
    send = {}  # send[r, i] = NIC injection start time for rank r, slot i
    recv = {}  # recv[r, i] = recv completion time (data available locally)
    for r in range(N):
        for i in range(total_slices):
            send[r, i] = model.addVar(name=f"s_{r}_{i}")
            recv[r, i] = model.addVar(name=f"rv_{r}_{i}")
    model.update()

    # Interleaved slot ordering (same as AllReduce)
    interleaved = []
    for step_in_ol in range(n_spp):
        for ol in range(n_ol):
            for s in range(S):
                interleaved.append((ol, step_in_ol, s))

    slot_of = {entry: i for i, entry in enumerate(interleaved)}

    for r in range(N):
        prev_r = topo.prev(r)
        is_inter_recv = topo.is_inter_node(prev_r, r)
        is_inter_send = topo.is_inter_node(r, topo.ring_next[r])
        inject = sig.slice_bytes * (net.G_inter if is_inter_send else net.G_intra)
        recv_bw = sig.slice_bytes * (net.G_inter if is_inter_recv else net.G_intra)
        l_recv = l if is_inter_recv else net.L_intra
        calc = sig.calc_reduce_ns

        for i in range(total_slices):
            ol, ps, s = interleaved[i]

            # NIC serialization: send[r,i] >= send[r,i-1] + inject
            if i > 0:
                model.addConstr(send[r, i] >= send[r, i - 1] + inject,
                                name=f"nic_{r}_{i}")
            else:
                model.addConstr(send[r, i] >= 0, name=f"init_{r}")

            # Send must wait for local recv completion + copy
            # (can't send data we haven't received yet)
            model.addConstr(send[r, i] >= recv[r, i] + calc + net.o,
                            name=f"sd_{r}_{i}")

            # Recv: data arrives from previous rank's send
            if ps > 0:
                prev_entry = (ol, ps - 1, s)
                prev_i = slot_of[prev_entry]
                model.addConstr(
                    recv[r, i] >= send[prev_r, prev_i] + l_recv + recv_bw + net.o,
                    name=f"xr_{r}_{i}",
                )
            else:
                # First step: data is local, recv is immediate
                model.addConstr(recv[r, i] >= 0, name=f"rv0_{r}_{i}")

    t = model.addVar(name="t")
    for r in range(N):
        is_inter_send = topo.is_inter_node(r, topo.ring_next[r])
        inject = sig.slice_bytes * (net.G_inter if is_inter_send else net.G_intra)
        model.addConstr(t >= send[r, total_slices - 1] + inject + net.o,
                        name=f"obj_{r}")
    model.setObjective(t, gp.GRB.MINIMIZE)
    model.update()
    return model


def solve_collective(sig: CollectiveSignature,
                     L_max: float = 1_000_000) -> CollectiveResult:
    """
    Full pipeline: generate GOAL → build dep graph → LPConverter → sweep → extract piecewise.

    Uses the exact same LP formulation as the monolithic Full LP,
    guaranteeing identical results for single collectives.
    """
    import tempfile
    t0 = time.time()

    # --- Step 1: Generate GOAL text for this collective ---
    _prepend_sys_path(_resolve_generator_dir())

    from nccl_comm import (
        AllReduce as NCCLAllReduce, AllGather as NCCLAllGather,
        ReduceScatter as NCCLReduceScatter,
        Communicator, CollInfo, CollChnlInfo, CollAlgo, NCCLProto,
    )
    from nccl_primitives import init_data, init_generation_flags
    from goal import GoalOpAtom, GoalSend, GoalRecv, GoalRank, GoalCPU

    # Ensure npkit data is loaded
    npkit_simple, npkit_ll = _resolve_npkit_paths()
    init_data(str(npkit_simple), str(npkit_ll))

    intra_env = os.environ.get("LLAMP_NCCL_ENABLE_INTRA_NODE_TRANSFER")
    if intra_env is not None:
        enabled = intra_env.strip().lower() not in {"0", "false", "no"}
        init_generation_flags(False, False, enabled)

    topo = sig.ring_topology
    N = sig.n_ranks
    n_ch = sig.n_channels

    # Build GPU IDs and communicator
    gpu_ids = [(f"node{topo.rank_to_node[r]}", r) for r in range(N)]
    comm = Communicator("comp_comm", gpu_ids)

    # Add ring topologies: use sig.ring_topology for channel 0,
    # and sig.extra_ring_topologies for additional channels (if provided).
    extra_topos = getattr(sig, 'extra_ring_topologies', None) or []
    all_topos = [topo] + list(extra_topos)
    # Pad with channel 0's topology if fewer topologies than channels
    while len(all_topos) < n_ch:
        all_topos.append(topo)
    for ch_topo in all_topos:
        for rank in range(N):
            nxt = ch_topo.ring_next[rank]
            prev = next(r for r in range(N) if ch_topo.ring_next[r] == rank)
            comm.add_ring_topo(rank, prev, nxt)

    # Map collective type
    coll_map = {
        "allreduce": NCCLAllReduce,
        "allgather": NCCLAllGather,
        "reducescatter": NCCLReduceScatter,
    }
    coll_class = coll_map.get(sig.collective_type)
    if coll_class is None:
        raise NotImplementedError(f"Unsupported: {sig.collective_type}")

    # type_size: collectives with reduce ops use the element type (4 for fp32),
    # copy-only collectives (allgather) use 1 (byte-level chunking).
    ts = 1 if sig.collective_type == "allgather" else 4
    coll_info = CollInfo(
        root_rank=0, red_op=0,
        algo=CollAlgo.RING, proto=NCCLProto.SIMPLE,
        data_size=sig.data_bytes, type_size=ts,
        chunk_steps=sig.slices_per_step * 2,
        slice_steps=2,
        step_size=sig.slice_bytes // 2,
    )

    # Per-channel work/chunk info
    work_count_per_ch = sig.data_bytes // (ts * n_ch)
    chunk_count = sig.slice_bytes // ts
    coll_chnl_infos = []
    for ch in range(n_ch):
        coll_chnl_infos.append(CollChnlInfo(
            count=work_count_per_ch, chunk_count=chunk_count,
            work_count=work_count_per_ch, last_chunk_count=chunk_count,
            work_offset=ch * work_count_per_ch, send_buff=0, recv_buff=0,
        ))

    # Generate GOAL text for all ranks
    gpu_id2goal_rank = {gid: i for i, gid in enumerate(gpu_ids)}
    goal_lines = [f"num_ranks {N}\n"]

    for rank in range(N):
        GoalOpAtom.task_id_for_rank = {}
        GoalSend.send_message_id = {}
        GoalRecv.recv_message_id = {}

        coll = coll_class(gpu_ids[rank], comm, coll_info, coll_chnl_infos, context=1)
        primitives = coll.to_primitives()
        goal_op, _ = primitives.to_goal(gpu_id2goal_rank, 0, 0)
        rank_lines = list(goal_op.generate_lines())

        goal_lines.append(f"\nrank {rank} {{\n")
        for line in rank_lines:
            goal_lines.append(f"{line}\n")
        goal_lines.append("}\n")

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.goal', delete=False) as f:
        f.writelines(goal_lines)
        goal_path = f.name

    try:
        # --- Step 2: Build dep graph and LP (same as Full LP) ---
        # Add LLAMP LP code to path
        _prepend_sys_path(Path(__file__).resolve().parents[1])

        from dep_graph_generator import DependencyGraphGenerator
        from lp_converter import LPConverter

        gen = DependencyGraphGenerator(goal_path, None)
        dg = gen.generate(False)
        rnm = {r: int(topo.rank_to_node[r]) for r in range(N)}

        nic_per_rank_env = os.environ.get("LLAMP_NCCL_NIC_PER_RANK", "")
        nic_per_rank = nic_per_rank_env.strip().lower() in {"1", "true", "yes"}
        nics_per_node = int(os.environ.get("LLAMP_NCCL_NICS_PER_NODE", "1"))

        model = LPConverter(
            dg, o=int(sig.network.o),
            rank_node_map=rnm,
            l_intra=sig.network.L_intra,
            g_intra=sig.network.G_intra,
            nic_per_rank=nic_per_rank,
            nics_per_node=nics_per_node,
        ).convert_to_lp(verbose=False, G=sig.network.G_inter)

        # --- Step 3: Sweep and extract piecewise ---
        model.setParam("LogToConsole", 0)
        model.setParam("Method", 1)
        l_var = model.getVarByName("l")

        L_points = list(range(0, int(L_max) + 1, 5000))
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
        piecewise = PiecewiseAffine(pieces=pieces)

        # --- Step 4: Extract NIC/CPU finish times at L=0 ---
        # This enables the composition to model NIC-gap overlap:
        # the NIC transitions between collectives without gap delays.
        #
        # We extract per-RANK finish times for rank 0 (not global max).
        # nic_finish = when rank 0's NIC finishes injecting all its sends.
        # cpu_finish = when rank 0's last recv/calc completes.
        # The NIC chain across collectives models rank 0's NIC queue.
        l_var.lb = 0
        model.optimize()
        from dep_graph import VertexType
        nic_finish = 0.0
        cpu_finish = 0.0
        for v in dg.graph.vs:
            if v["r"] != 0:  # rank 0 only
                continue
            var = model.getVarByName(f"y{v.index}")
            if var is None:
                continue
            if v["type"] == VertexType.SEND:
                dst_r = v["dst_r"] if "dst_r" in v.attributes() else -1
                src_node = rnm.get(0, -1)
                dst_node = rnm.get(dst_r, -1)
                G = sig.network.G_intra if src_node == dst_node else sig.network.G_inter
                send_finish = var.X + v["cost"] * G
                nic_finish = max(nic_finish, send_finish)
            else:
                cost = v["cost"] if v["cost"] else 0
                if v["type"] == VertexType.RECV:
                    op_finish = var.X + sig.network.o
                elif v["type"] == VertexType.CALC:
                    op_finish = var.X + cost
                else:
                    continue
                cpu_finish = max(cpu_finish, op_finish)

        elapsed = time.time() - t0

        return CollectiveResult(
            signature=sig,
            piecewise=piecewise,
            lp_vars=model.NumVars,
            lp_constrs=model.NumConstrs,
            solve_time_s=elapsed,
            nic_finish_ns=nic_finish,
            cpu_finish_ns=cpu_finish,
        )
    finally:
        os.unlink(goal_path)
