# SC Tracing Artifact

This repository supports the SC paper, "Provisioning Networks for AI Supercomputers: A Trace-Driven Study of Performance Sensitivity at Unprecedented Scale".

The artifact takes NCCL/AI workload traces that have already been converted to GOAL-like schedules, replays or analyzes them with LogGOPSim and LP tooling, and regenerates the paper figures from packaged CSV outputs. The cleaned workflow is intentionally tiered: reviewers can run the cheap packaged path on a laptop, while deeper GOAL and LP revalidation can be run on a larger machine with Gurobi and matching sidecars.

Work for this cleanup/revalidation pass lives on branch `clean_version`.

## What Is Included

- `scripts/`: figure-generation and comparison scripts.
- `data/output/` and `data/workspaces/`: packaged CSVs and intermediate outputs used by the paper figure scripts.
- `data/traces/demo_allreduce_16r_1MiB.goal`: a tiny GOAL trace for local LogGOPSim and LP smoke tests.
- `pipeline/`: user-facing wrappers for LogGOPSim replay, GOAL sidecar generation, raw NSYS conversion, and LP runs.
- `solver/`: dependency-graph and LP tooling for Composite-LP/Monolithic-LP style analyses.
- `tools/LogGOPSim/`: vendored/patched LogGOPSim source used by replay wrappers.
- `tools/nccl_generator/`: NCCL trace converter for optional raw NSYS SQLite to GOAL plus metadata sidecars.
- `docs/progress_log.md` and `docs/revalidation_report.md`: evidence from the cleanup/revalidation pass.

Raw tracing is not part of the normal artifact path. Use released GOAL traces and packaged intermediate outputs unless you are explicitly validating the optional NSYS conversion path.

## Tier A: Packaged Figure Reproduction

This path uses packaged CSVs only. It does not need GPUs, raw NSYS traces, Gurobi, or large GOAL files.

```bash
git clone -b clean_version https://github.com/tommasobo/SC_Tracing.git
cd SC_Tracing
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce_all.py
```

Outputs are written to `figures/`. On the cleanup machine (`bigmem`, Ubuntu 24.04, Python 3.12), this completed in about 22 seconds with about 190 MiB peak RSS.

Useful variants:

```bash
python reproduce_all.py --list
python reproduce_all.py --only 3 6 10
```

## Tier B: Demo and Real GOAL LogGOPSim Replay

System packages needed for building LogGOPSim:

```bash
sudo apt-get install g++ gengetopt re2c
```

Run the bundled synthetic demo:

```bash
python pipeline/demo.py
```

The demo writes:

```text
data/demo_output/lgs_points.csv
```

Equivalent direct command:

```bash
python pipeline/run_lgs_sweep.py \
  --goal data/traces/demo_allreduce_16r_1MiB.goal \
  --out data/demo_output/lgs_points.csv \
  --latencies 0 1000 10000 100000
```

To also verify the small LP path with a generated sidecar:

```bash
python pipeline/demo.py --with-lp
```

Released GOAL traces are indexed at:

```text
http://storage2.spcl.ethz.ch/traces/ai/
```

Download only the GOAL files you need. Large local inputs should go under `data/external/`, which is ignored by git.

Example, Grok 314B N4/GPU16:

```bash
mkdir -p data/external/grok_N4 data/revalidation/grok_N4_lgs
curl -L -o data/external/grok_N4/grok.goal \
  http://storage2.spcl.ethz.ch/traces/ai/grok/Grok314B_N4_GPU16_TP4_PP1_CP1_VP1_EP4_ETP4_GBS256/grok.goal
curl -L -o data/external/grok_N4/SHA256SUMS \
  http://storage2.spcl.ethz.ch/traces/ai/grok/Grok314B_N4_GPU16_TP4_PP1_CP1_VP1_EP4_ETP4_GBS256/SHA256SUMS
(cd data/external/grok_N4 && sha256sum -c SHA256SUMS --ignore-missing)
python pipeline/run_lgs_sweep.py \
  --goal data/external/grok_N4/grok.goal \
  --out data/revalidation/grok_N4_lgs/lgs_points.csv \
  --latencies 0 4000 10000 \
  --G 0.04 --o 200
```

Example, vLLM Llama 70B N2/GPU8:

```bash
mkdir -p data/external/vllm_llama70b_N2 data/revalidation/vllm_llama70b_N2_lgs
curl -L -o data/external/vllm_llama70b_N2/vllm_llama_N2_GPU8_PP8.goal \
  http://storage2.spcl.ethz.ch/traces/ai/vllm/Llama_3.1_70B_Instruct_N2_GPU8_TP8_Short_Prompts/vllm_llama_N2_GPU8_PP8.goal
python pipeline/run_lgs_sweep.py \
  --goal data/external/vllm_llama70b_N2/vllm_llama_N2_GPU8_PP8.goal \
  --out data/revalidation/vllm_llama70b_N2_lgs/lgs_points.csv \
  --latencies 0 4000 10000 \
  --G 0.04 --o 200
```

## Tier C: GOAL Plus `comm_dep` LP Regeneration

LP regeneration requires Gurobi and a communication-dependency sidecar. Install optional solver dependencies:

```bash
python -m pip install -r requirements-solver.txt
```

Verify Gurobi:

```bash
python -c "import gurobipy as gp; m=gp.Model(); x=m.addVar(lb=0); m.setObjective(x, gp.GRB.MAXIMIZE); m.addConstr(x <= 1); m.optimize(); print(m.Status, m.ObjVal)"
```

The LP sidecar is a four-column CSV:

```text
src_rank,src_label_offset,dst_rank,dst_label_offset
```

Preferred sidecar generation path:

```bash
python pipeline/run_lgs.py \
  --goal path/to/output.goal \
  --L 1000 --G 0.04 --o 200 \
  --comm-dep-out path/to/comm_dep.csv
```

Fallback sidecar generation from GOAL text alone:

```bash
python pipeline/generate_comm_dep_from_goal.py \
  --goal path/to/output.goal \
  --out path/to/comm_dep.csv
```

The fallback is useful for diagnostics and validated on the demo, Grok N4, and a local Llama7B N2 trace, but it is not universally safe. For vLLM Llama70B N2, tag-only FIFO matching produces a cyclic LP graph even though every send/recv is paired; the trace needs true upstream match/dependency information.

For most data-level regeneration tasks, use the orchestration driver instead of chaining the lower-level scripts manually. From an existing GOAL:

```bash
python pipeline/regenerate_from_inputs.py \
  --goal path/to/output.goal \
  --out-dir data/revalidation/workload \
  --comm-dep-mode auto \
  --lgs-latencies 0 4000 10000 \
  --monolithic-latencies 0 4000 \
  --ranks-per-node 4 \
  --l-intra 350 --g-intra 0.00333 \
  --o 200 --G 0.04 --add-barriers
```

From NSYS-exported SQLite files, use the same driver with `--sqlite-dir`; it first invokes `pipeline/run_nccl_generator.py` and then emits/validates the LP `comm_dep.csv`:

```bash
python pipeline/regenerate_from_inputs.py \
  --sqlite-dir path/to/nsys_sqlite_dir \
  --out-dir data/revalidation/workload \
  --lgs-latencies 0 4000 \
  --monolithic-latencies 0 4000
```

By default, `--comm-dep-mode auto` uses an existing `--comm-dep` if supplied, otherwise patched LogGOPSim. The driver validates that the sidecar is non-empty and has four integer columns. Use `--allow-goal-fallback` only for diagnostics or traces already known to match the LogGOPSim sidecar exactly.

Run Monolithic-LP:

```bash
python pipeline/run_monolithic_lp.py \
  --goal path/to/output.goal \
  --comm-dep path/to/comm_dep.csv \
  --out data/revalidation/workload/full_runtime.csv \
  --l-min 0 --l-max 1000000 --step 50000 \
  --l-intra 350 --o 200 --G 0.04
```

For node-scaling or hardware-comparison checks where only a few latency
points are needed, use the exact-point runner. It builds the full LP once
and solves only the requested latency values:

```bash
python pipeline/run_monolithic_points.py \
  --goal path/to/output.goal \
  --comm-dep path/to/comm_dep.csv \
  --out data/revalidation/workload/monolithic_points.csv \
  --latencies 0 4000 \
  --ranks-per-node 4 \
  --l-intra 350 --g-intra 0.00333 \
  --o 200 --G 0.04 --add-barriers
```

Run the GOAL-level LP sensitivity wrapper when the GOAL and LP sidecar are
available. This path builds a dependency graph from the full GOAL trace and
therefore requires `comm_dep.csv` for real NCCL traces:

```bash
python pipeline/run_composite_lp.py \
  --goal path/to/output.goal \
  --comm-dep path/to/comm_dep.csv \
  --out data/revalidation/workload/composed_runtime.csv \
  --l-min 0 --l-max 1000000 --step 50000 \
  --l-intra 350 --o 200 --G 0.04
```

Both GOAL-level LP wrappers fail early if `--comm-dep` is missing or empty. Use `--allow-tag-match` only for known-simple synthetic traces.

Run the paper-style NCCL Composite-LP path when the NCCL metadata sidecars are
available. This path does not use `comm_dep.csv`; it reads
`collective_instances.csv` and `comm_ring_info.csv`, solves unique collective
motifs, and composes the program-level curve:

```bash
python pipeline/run_nccl_composite.py \
  --analysis-dir path/to/analysis \
  --out data/revalidation/workload/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/workload/collective_cache \
  --clear-cache --parallel-solve --max-workers 8
```

By default this wrapper uses each row's NCCL communicator size
(`--rank-count-mode row-nranks`). This matches the newer Grok replay driver and
avoids a legacy shortcut where one global `nranks` value was accidentally reused
for all collective motifs. The legacy behavior is still available with
`--rank-count-mode first-row` when comparing against old scratch outputs.

For Grok, the cleaned wrapper has been validated through N512 using copied
per-motif caches from the development replay outputs. N8, N16, N32, N64, N128,
N256, and N512 reproduce those replay Composite-LP curves exactly over
`L=0..1e6 ns`. N4 has two usable paths: the old replay cache is a legacy
16-rank/global-rank run, while the cleaned default regenerates 4-rank row-nranks
motifs from the metadata.

N256 was also regenerated from a cold cache on the high-RAM machine:
16 Composite signatures solved in 31m36s wall time with 8.0 GiB peak RSS from
`/usr/bin/time`, matching the development replay curve within 0.0023% max
relative difference.

The high-RAM Grok node-scaling aggregation used during revalidation is:

```bash
python scripts/grok_node_scaling.py \
  --scratch-root /mnt/scratch/GrokStudy/repo \
  --extra-scratch-root /mnt/scratch/GrokStudyCodex/Traces_Compression \
  --out-dir results/revalidation/grok_node_scaling \
  --nodes 4 8 16 32 64 128 256 512 \
  --target-latency 0 \
  --target-latencies 0 4000 10000 250000 500000 1000000 \
  --no-packaged-large \
  --exclude-monolithic
```

It combines hardware wall times from `collective_instances.csv`, regenerated
Composite-LP curves under `data/revalidation/` where available, existing LGS
curves or `stats/lgs_L*.json` points, and Monolithic-LP points only where they
already exist. The command above intentionally excludes packaged N512/N1024
rows; with the development replay workspace available, N512 is included from
real metadata instead. The command does not launch any Monolithic-LP solves. The multi-latency mode writes
per-latency CSV/JSON summaries plus
`grok_node_scaling_multi_latency.{png,pdf}`.

## Tier D: Optional Raw NSYS SQLite to GOAL

This path is not needed for normal artifact reproduction. It exists to document how raw NSYS SQLite exports can be converted to GOAL plus NCCL metadata sidecars:

```bash
python -m pip install -r requirements-tierc.txt
python pipeline/run_nccl_generator.py \
  --sqlite-dir /path/to/nsys_sqlite_dir \
  --out-dir /path/to/analysis
```

This writes `output.goal`, `collective_instances.csv`, `goal_label_ranges.csv`, `comm_info.csv`, `comm_ring_info.csv`, and related NCCL metadata. It does not write the LP `comm_dep.csv`; generate that from the produced GOAL with `pipeline/run_lgs.py --comm-dep-out`.

For the guarded Fig. 5 NSYS pipeline:

```bash
bash pipeline/reproduce_fig5_from_nsys.sh --dry-run
bash pipeline/reproduce_fig5_from_nsys.sh --run-lp
```

The `--run-lp` mode can take substantial time and requires Gurobi.

## Comparing Regenerated CSVs

Use the numeric comparison helper instead of relying only on plots:

```bash
python scripts/compare_csv.py \
  --expected path/to/packaged_or_prior.csv \
  --actual path/to/new.csv \
  --out-dir results/revalidation/workload \
  --label my_check \
  --points actual
```

It writes a detailed CSV and JSON summary with absolute and relative differences.

## Expensive Or Skipped Paths

- Do not retrace workloads or recollect GOAL traces as part of normal artifact reproduction.
- Do not rerun 4096-GPU Grok cases unless a specific gap justifies the cost.
- Use packaged outputs for 4096-GPU Monolithic-LP and full-scale replay baselines.
- Moderate GOAL replay from released traces is feasible and useful for sanity checks.
- LP regeneration is feasible only when GOAL and matching `comm_dep` information are both available.

## Tests

For development validation:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/check_artifact.py --skip-figure
```

Cleanup result after this pass: `13 passed` on `bigmem`.

## Current Validation Status

During the `clean_version` cleanup pass:

- Packaged figures regenerated successfully from bundled CSVs.
- Vendored LogGOPSim builds on the current GCC toolchain.
- Real downloaded GOAL traces for Grok N4/GPU16 and vLLM N2/GPU8 replay through LogGOPSim.
- Real Monolithic-LP regeneration succeeded for Grok N4/GPU16 and a local Llama7B N2/GPU8 trace when a valid `comm_dep` sidecar was generated.
- Real NCCL metadata-sidecar Composite-LP regeneration succeeded for Grok N4, N8, N16, N32, and N64; regenerated curves match existing scratch baselines within `0.014%` max relative difference.
- LGS/LP numeric comparisons were saved under `results/revalidation/`.
- The `comm_dep` issue is root-caused for vLLM N2: GOAL-only matching is insufficient for that trace and the patched LogGOPSim sidecar writer emits an empty file.

See `docs/progress_log.md` for commands and `docs/revalidation_report.md` for the workload matrix and detailed sidecar analysis.
