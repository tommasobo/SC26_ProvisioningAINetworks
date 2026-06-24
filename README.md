# SC Tracing Artifact

This repository supports the SC paper, "Provisioning Networks for AI Supercomputers: A Trace-Driven Study of Performance Sensitivity at Unprecedented Scale".

The artifact takes NCCL/AI workload traces that have already been converted to GOAL-like schedules, replays or analyzes them with LogGOPSim and Composite-LP tooling, and regenerates the paper figures from packaged CSV outputs. It is organized so a user can run the cheap figure path immediately, then optionally run deeper validation from downloaded GOAL traces.

Work for the cleanup/revalidation pass lives on branch `clean_version`.

## What Is Included

- `scripts/`: figure-generation scripts for paper figures 1, 3, 4, 5, 6, 7, 8/9, and 10.
- `data/output/` and `data/workspaces/`: packaged CSVs and intermediate outputs used by the figure scripts.
- `data/traces/demo_allreduce_16r_1MiB.goal`: a tiny GOAL trace for LogGOPSim smoke tests.
- `pipeline/`: user-facing wrappers for LogGOPSim replay and Composite-LP runs.
- `solver/`: dependency-graph and LP tooling for Composite-LP/Monolithic-LP style analyses.
- `tools/LogGOPSim/`: vendored LogGOPSim source used by the replay wrappers.
- `docs/progress_log.md`: running cleanup/revalidation log with commands, runtimes, inputs, outputs, and known limitations.

Raw NSYS tracing and GOAL recollection are intentionally out of scope for this cleanup. Use the released GOAL traces and packaged intermediate outputs instead.

## Quick Start: Regenerate Paper Figures

This path uses packaged CSVs only. It does not need GPUs, raw NSYS traces, Gurobi, or the large GOAL files.

```bash
git clone -b clean_version https://github.com/tommasobo/SC_Tracing.git
cd SC_Tracing
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce_all.py
```

Outputs are written to `figures/`. On the cleanup machine (`bigmem`, Ubuntu 24.04, Python 3.12), this completed in about 22 seconds with about 190 MiB peak RSS.

To list the figure mapping:

```bash
python reproduce_all.py --list
```

To regenerate a subset:

```bash
python reproduce_all.py --only 3 6 10
```

## LogGOPSim Demo

The demo builds the vendored LogGOPSim source if needed, replays the tiny shipped GOAL trace at four latency points, and writes a CSV.

System packages needed for building LogGOPSim:

```bash
sudo apt-get install g++ gengetopt re2c
```

Run:

```bash
python pipeline/demo.py
```

Output:

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

## Replay Released GOAL Traces

The public trace index is:

```text
http://storage2.spcl.ethz.ch/traces/ai/
```

Download only the GOAL files you need. Do not download raw NSYS traces unless you are explicitly redoing trace conversion. Large local inputs should go under `data/external/`, which is ignored by git.

Example: Grok 314B, N4/GPU16:

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

Example: vLLM Llama 70B, N2/GPU8:

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

Cleanup results from `bigmem`:

- vLLM N2/GPU8 replay: 147 MiB GOAL, 5,799,631 lines, 14.1 seconds for three points, 307 MiB peak RSS. Runtime was flat at 261.198 ms for 0, 4, and 10 us.
- Grok N4/GPU16 replay: 213 MiB GOAL, 8,080,201 lines, 35.6 seconds for three points, 575 MiB peak RSS. Runtime was 6125.226 ms at 0 us and 6125.367 ms at 10 us.

## Composite-LP Runs

Install the optional solver dependencies:

```bash
python -m pip install -r requirements-solver.txt
```

Composite-LP also requires a working Gurobi license. Verify it with:

```bash
python -c "import gurobipy as gp; m=gp.Model(); x=m.addVar(lb=0); m.setObjective(x, gp.GRB.MAXIMIZE); m.addConstr(x <= 1); m.optimize(); print(m.Status, m.ObjVal)"
```

Run the wrapper on a GOAL trace with its matching `comm_dep` sidecar:

```bash
python pipeline/run_composite_lp.py \
  --goal path/to/output.goal \
  --comm-dep path/to/InterNode_MicroEvents_Dependency.exact.comm_dep.csv \
  --out data/revalidation/workload/composed_runtime.csv \
  --l-min 0 --l-max 1000000 --step 50000 \
  --l-intra 350 --o 200
```

Important: many released GOAL files cannot be matched by tag alone. If `--comm-dep` is missing, the solver may fail after parsing with unmatched sends/recvs. The packaged paper figures therefore use precomputed Composite-LP CSVs under `data/output/` and `data/workspaces/`.

## Expensive Or Skipped Paths

- Do not retrace workloads or recollect GOAL traces as part of normal artifact reproduction.
- Do not rerun 4096-GPU Grok LogGOPSim replay unless there is a strong reason; the GOAL schedule is too large for routine validation.
- Use packaged outputs for 4096-GPU Monolithic-LP and full-scale replay baselines.
- Moderate GOAL replay from released traces is feasible and useful for sanity checks.
- Composite-LP regeneration is feasible only when the corresponding GOAL and comm-dep metadata are both available.

## Tests

For development validation:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Cleanup result: `7 passed in 1.92s` on `bigmem`.

## Current Validation Status

During the `clean_version` cleanup pass:

- Packaged figures regenerated successfully from the bundled CSVs.
- Vendored LogGOPSim was patched for modern GCC by adding the missing `<cstring>` include.
- The LogGOPSim demo now writes a real CSV output.
- Real downloaded GOAL traces for vLLM N2/GPU8 and Grok N4/GPU16 replay successfully through LogGOPSim.
- Composite-LP wrapper path handling was fixed, but real downloaded GOAL-only runs still require the matching comm-dep sidecar.
- Solver tests were repaired and now run from the repository root.

See `docs/progress_log.md` for exact commands, runtimes, memory, output paths, and limitations.
