# SC Tracing Cleanup Revalidation Report

Date: 2026-06-24

Repository: `/home/hpcuser/SC_Tracing`

Branch: `clean_version`

Initial artifact commit: `90231b14a03b526b406fb4811229b5544cc2a5c4`

Machine: `bigmem`, Ubuntu 24.04, Linux `6.8.0-1044-azure`, 416 logical CPUs, 10 TiB RAM, Python 3.12.3

## 1. Successfully Reproduced

The packaged figure path reproduces the scripted paper figures from bundled CSV/intermediate data without requiring GPUs, raw NSYS traces, Gurobi, or large GOAL files.

Command:

```bash
python3 reproduce_all.py
```

Result on `bigmem`: success in 22.20 seconds wall clock with 189,364 KiB peak RSS. Outputs were written under `figures/`.

The packaged pipeline path also succeeds after patching vendored LogGOPSim for the current GCC toolchain.

Command:

```bash
python3 reproduce_all.py --pipeline
```

Result on `bigmem`: success in 22.26 seconds wall clock with 190,868 KiB peak RSS. It built/used `tools/LogGOPSim`, ran the tiny shipped allreduce GOAL demo, wrote `data/demo_output/lgs_points.csv`, then regenerated figures from packaged CSVs.

The Python solver/unit tests now run from the repository root.

Command:

```bash
.venv/bin/python -m pytest -q
```

Result on `bigmem`: `7 passed in 1.92s`.

Gurobi is available through Python on this machine. A fresh `gurobipy` 13.0.1 smoke test solved a one-variable LP to optimality with objective `1.0`. The `gurobi_cl` executable was not required for the artifact wrappers.

## 2. Revalidated From Existing Traces

Two released GOAL traces were downloaded from `http://storage2.spcl.ethz.ch/traces/ai/` and replayed through the vendored LogGOPSim wrapper. The large local inputs and generated validation CSVs are ignored by git under `data/external/` and `data/revalidation/`.

Grok 314B N4/GPU16:

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

Result: 213 MiB GOAL, 8,080,201 lines, checksum passed for `grok.goal`, three-point replay completed in 35.61 seconds with 574,892 KiB peak RSS. Runtime was 6125.225735 ms at `L=0 ns`, 6125.301013 ms at `L=4000 ns`, and 6125.367143 ms at `L=10000 ns`.

vLLM Llama 70B N2/GPU8:

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

Result: 147 MiB GOAL, 5,799,631 lines, three-point replay completed in 14.10 seconds with 307,172 KiB peak RSS. Runtime was flat at 261.198144 ms for `L=0 ns`, `L=4000 ns`, and `L=10000 ns`.

## 3. Not Reproduced And Why

Composite-LP from a downloaded GOAL alone was not reproduced. The wrapper now resolves paths correctly, but the solver still requires matching communication-dependency metadata for many real traces. A vLLM GOAL-only probe parsed more than 5 million lines, then failed with unmatched sends/recvs because no `comm_dep` sidecar was available.

Probe command:

```bash
timeout 600 python3 pipeline/run_composite_lp.py \
  --goal data/external/vllm_llama70b_N2/vllm_llama_N2_GPU8_PP8.goal \
  --out data/revalidation/vllm_lp_smoke/composed_runtime.csv \
  --l-min 0 --l-max 8000 --step 4000 \
  --l-intra 350 --o 200
```

Full 4096-GPU cases were intentionally not rerun. The cleanup goal is reproducibility and validation using existing traces/intermediates; rerunning the largest cases would consume the high-RAM window without materially improving the user-facing artifact unless a specific missing result is identified.

Raw NSYS retracing and GOAL recollection were not attempted by design.

## 4. Clean Artifact Location

Use this repository and branch as the cleaned artifact:

```bash
git clone -b clean_version https://github.com/tommasobo/SC_Tracing.git
cd SC_Tracing
```

The local branch contains documentation, test, pipeline, and portability changes that are not present in the initial artifact commit unless they are committed/pushed later.

## 5. Exact Commands For Future Users

Packaged figure reproduction:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce_all.py
```

List or subset figures:

```bash
python reproduce_all.py --list
python reproduce_all.py --only 3 6 10
```

Run the bundled LogGOPSim smoke pipeline:

```bash
sudo apt-get install g++ gengetopt re2c
python reproduce_all.py --pipeline
```

Run only the tiny LogGOPSim demo:

```bash
python pipeline/demo.py
```

Run solver tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Run Composite-LP when a matching `comm_dep` sidecar is available:

```bash
python -m pip install -r requirements-solver.txt
python pipeline/run_composite_lp.py \
  --goal path/to/output.goal \
  --comm-dep path/to/InterNode_MicroEvents_Dependency.exact.comm_dep.csv \
  --out data/revalidation/workload/composed_runtime.csv \
  --l-min 0 --l-max 1000000 --step 50000 \
  --l-intra 350 --o 200
```

## 6. Remaining TODOs Ranked By Importance

1. Locate and publish the matching `comm_dep` sidecars for released GOAL traces, or document precisely which packaged workspaces contain equivalent dependency metadata.
2. Add one small, fully reproducible Composite-LP run from GOAL plus `comm_dep` to close the gap between packaged CSV reproduction and trace-level LP regeneration.
3. Compare regenerated PDFs visually or numerically against the submitted paper figures and record any differences due to plotting versions or data updates.
4. Decide whether selected small revalidation CSVs under `data/revalidation/` should be committed, attached as release artifacts, or left as regenerated local outputs.
5. Add optional caching for `txt2bin` conversion in `pipeline/run_lgs_sweep.py` if users will run large latency grids on the same GOAL trace.
6. Inspect the development repository history further only if a missing solver-sidecar workflow or paper script is still needed; the artifact repository is now sufficient for the packaged figure path and moderate GOAL replay.
