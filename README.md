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

For large GOAL files, keep both the txt2bin cache and any temporary binary
traces on a large scratch filesystem. Otherwise `txt2bin`/LogGOPSim can fail
with filesystem or `SIGBUS` errors if `/tmp` is small:

```bash
python pipeline/run_lgs_sweep.py \
  --goal /mnt/scratch/workspaces/grok/N128/analysis/output.goal \
  --out results/revalidation/grok_N128_lgs/lgs_runtime.csv \
  --latencies 0 4000 10000 250000 500000 1000000 \
  --G 0.04 --o 200 \
  --bin-cache-dir /mnt/scratch/SC_Tracing_lgs_cache/grok_N128 \
  --tmp-dir /mnt/scratch/SC_Tracing_lgs_cache/_tmp
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

The fallback is useful for diagnostics and validated on the demo, Grok N4, and a local Llama7B N2 trace, but it is not universally safe. For the public prebuilt vLLM Llama70B N2 GOAL, tag-only FIFO matching produces a cyclic LP graph even though every send/recv is paired; that public GOAL needs true upstream match/dependency information for LP.

For V2 NCCL generator inputs, the expected flow is regenerable: one GOAL rank
per GPU plus metadata sidecars are produced from NSYS SQLite by
`pipeline/run_nccl_generator.py`, and the LP `comm_dep.csv` can then be emitted
from that GOAL by patched LogGOPSim. This has been validated end-to-end on the
online vLLM Llama70B N2 NSYS reports. If only a public GOAL is available and its
matching V2 metadata/raw SQLite is missing, the fallback matcher may not be
correct enough for Monolithic-LP.

For most data-level regeneration tasks, use the orchestration driver instead of chaining the lower-level scripts manually. From an existing GOAL:

```bash
python pipeline/regenerate_from_inputs.py \
  --goal path/to/output.goal \
  --out-dir data/revalidation/workload \
  --comm-dep-mode auto \
  --bin-cache-dir /mnt/scratch/SC_Tracing_lgs_cache \
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
  --bin-cache-dir /mnt/scratch/SC_Tracing_lgs_cache \
  --lgs-latencies 0 4000 \
  --monolithic-latencies 0 4000
```

By default, `--comm-dep-mode auto` uses an existing `--comm-dep` if supplied, otherwise patched LogGOPSim. The driver validates that the sidecar is non-empty and has four integer columns. Use `--allow-goal-fallback` only for diagnostics or traces already known to match the LogGOPSim sidecar exactly.
When `--bin-cache-dir` is provided, lower-level LGS calls place temporary
conversion files next to that cache by default; pass `--tmp-dir` to
`pipeline/run_lgs.py` or `pipeline/run_lgs_sweep.py` directly if you need a
specific scratch location.

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

If a trace has multiple stream IDs, the wrapper now checks whether collective
time intervals actually overlap before composing per-stream timelines. Multiple
stream IDs without overlap are composed as one sequential rank timeline. Use
`--force-parallel-streams` only for diagnostics that intentionally preserve the
earlier cleaned-wrapper behavior.

Some older packaged curves used historical motif-LP settings. The Llama7B N32
figure bundle is reproduced with one NIC queue per rank and sequential rank-0
composition:

```bash
/usr/bin/time -v timeout 7200 python pipeline/run_nccl_composite.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out data/revalidation/figures_end_to_end/llama7b_n32_composite_packaged_mode/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/figures_end_to_end/llama7b_n32_composite_packaged_mode/collective_cache \
  --clear-cache --parallel-solve --max-workers 8 \
  --node-map-mode rank-block --force-sequential --nic-per-rank
```

This cold-cache run completed in 19m26s on `bigmem` and reproduced
`data/workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/composed_runtime.csv`
within 0.0276% max relative difference. Without `--nic-per-rank`, the same
metadata regenerates a different lower-cost motif family and is not comparable
to the packaged paper curve.

The fixed-latency bandwidth-sensitivity companion for the Llama7B N32 figure is:

```bash
/usr/bin/time -v timeout 7200 python pipeline/run_nccl_bw_sensitivity.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out data/revalidation/figures_end_to_end/llama7b_n32_bw_full/bandwidth_sensitivity.csv \
  --cache-dir data/revalidation/figures_end_to_end/llama7b_n32_bw_full/fixed_l_cache \
  --clear-cache --fixed-l-ns 4000 \
  --min-bw-gbps 10 --max-bw-gbps 1600 --num-points 20 --spacing log \
  --max-workers 8 --node-map-mode rank-block --force-sequential --nic-per-rank
```

This cold-cache run completed in 31m22s on `bigmem`, solving 20 bandwidth
points from the metadata sidecars. It reproduces the packaged bandwidth curve
within 0.6335% max relative difference and 0.0588% mean relative difference.
The remaining drift is concentrated at the high-bandwidth asymptote and is
documented as historical-driver/model provenance, not a cached-data shortcut.

Figure-level end-to-end evidence and the commands used are summarized in
`results/revalidation/figures_end_to_end/figure_end_to_end_summary.md`.
For a concise per-figure status table, including which figures are plot-only
versus data/model regenerated, see `docs/figure_reproduction_status.md`.

For Grok, the cleaned wrapper has been validated through N512 using copied
per-motif caches from the development replay outputs. N8, N16, N32, N64, N128,
N256, and N512 reproduce those replay Composite-LP curves exactly over
`L=0..1e6 ns`. N4 has two usable paths: the old replay cache is a legacy
16-rank/global-rank run, while the cleaned default regenerates 4-rank row-nranks
motifs from the metadata.

N64, N256, and N512 were also regenerated from cold caches on the high-RAM
machine. N64 solved 16 signatures in 47m13s with 1.60 GiB peak RSS and matched
the development replay curve within 0.000060% max relative difference. N256
solved 16 signatures in 31m36s with 8.0 GiB peak RSS and matched within
0.0023%. N512 solved 16 signatures in 2h31m43s with 30.5 GiB peak RSS and
matched within 0.0018%.

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
Composite-LP curves under `data/revalidation/` where available, and regenerated
or existing LGS curves. N128 now uses
`data/revalidation/grok_N128_lgs_regen/lgs_runtime.csv`, regenerated from the
16 GiB GOAL in 1h20m13s with 52.5 GiB peak RSS using a scratch-backed txt2bin
cache. The command above intentionally
excludes packaged N512/N1024 rows and excludes Monolithic-LP points; with the
development replay workspace available, N512 is included from real metadata
instead. The command does not launch any Monolithic-LP solves. The multi-latency mode writes
per-latency CSV/JSON summaries plus
`grok_node_scaling_multi_latency.{png,pdf}`.

### End-to-End Grok Composite Cold Runs

The large per-motif caches are intentionally not required for the artifact. To
recreate the corrected Composite-LP curves from metadata sidecars, run the
cold-cache commands below on the high-RAM machine. These do not require the LP
`comm_dep.csv` sidecar; they require `collective_instances.csv`,
`comm_ring_info.csv`, and the shipped `data/npkit/` calibration files.

N64 corrected cold run:

```bash
/usr/bin/time -v timeout 7200 python pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/GrokStudy/repo/workspaces/grok/N64/analysis_new \
  --out data/revalidation/grok_N64_composite_row_nranks_regen/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/grok_N64_composite_row_nranks_regen/collective_cache \
  --clear-cache --parallel-solve --max-workers 4
```

N256 corrected cold run:

```bash
/usr/bin/time -v timeout 7200 python pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/GrokStudyCodex/Traces_Compression/workspaces/grok/N256/analysis \
  --out data/revalidation/grok_N256_composite_row_nranks_regen/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/grok_N256_composite_row_nranks_regen/collective_cache \
  --clear-cache --parallel-solve --max-workers 4
```

N512 corrected cold run:

```bash
/usr/bin/time -v timeout 21600 python pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/GrokStudyCodex/Traces_Compression/workspaces/grok/N512/analysis \
  --out data/revalidation/grok_N512_composite_row_nranks_regen/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/grok_N512_composite_row_nranks_regen/collective_cache \
  --clear-cache --parallel-solve --max-workers 4
```

The revalidation run completed N64 in 47m13s, N256 in 31m36s, and N512 in
2h31m43s on `bigmem`. N512 exceeds the two-hour-per-plot budget used for the
final packaged-plot sweep, so treat it as an optional high-RAM validation run.

Compare regenerated curves numerically:

```bash
python scripts/compare_csv.py \
  --expected /mnt/scratch/GrokStudyCodex/Traces_Compression/output/grok_n512/comp/sweeps/composed_runtime.csv \
  --actual data/revalidation/grok_N512_composite_row_nranks_regen/comp/sweeps/composed_runtime.csv \
  --out-dir results/revalidation/grok_N512_composite_row_nranks_regen \
  --label grok_N512_cold_regen_vs_codex \
  --points actual
```

N128 Monolithic-LP is intentionally not part of this cleanup pass. N64
Monolithic-LP already took 2h27m and 184.5 GiB RSS for one latency point; N128
would be a separate expensive run and is not needed for the final no-monolithic
Grok scaling plot.

## Tier D: Optional Raw NSYS SQLite to GOAL

This path is not needed for normal artifact reproduction. It exists to document how raw NSYS SQLite exports can be converted to GOAL plus NCCL metadata sidecars:

```bash
python -m pip install -r requirements-tierc.txt
python pipeline/run_nccl_generator.py \
  --sqlite-dir /path/to/nsys_sqlite_dir \
  --out-dir /path/to/analysis
```

This writes `output.goal`, `collective_instances.csv`, `goal_label_ranges.csv`, `comm_info.csv`, `comm_ring_info.csv`, and related NCCL metadata. It does not write the LP `comm_dep.csv`; generate that from the produced GOAL with `pipeline/run_lgs.py --comm-dep-out`.

The online vLLM Llama70B N2 trace is a concrete raw-NSYS example:

```bash
mkdir -p /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/{nsys,sqlite,analysis_strict,commdep_strict,lgs_strict,composite_strict,bin_cache}
cd /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/nsys
wget -c --progress=dot:giga \
  http://storage2.spcl.ethz.ch/traces/ai/vllm/Llama_3.1_70B_Instruct_N2_GPU8_TP8_Short_Prompts/nsys_reports/nsys_report_nid006673_57756.nsys-rep \
  http://storage2.spcl.ethz.ch/traces/ai/vllm/Llama_3.1_70B_Instruct_N2_GPU8_TP8_Short_Prompts/nsys_reports/nsys_report_nid006679_8937.nsys-rep

for rep in /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/nsys/*.nsys-rep; do
  sqlite=/mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/sqlite/$(basename "${rep%.nsys-rep}.sqlite")
  nsys export --type=sqlite -o "$sqlite" "$rep"
done

cd /path/to/SC_Tracing
python pipeline/run_nccl_generator.py \
  --sqlite-dir /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/sqlite \
  --out-dir /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/analysis_strict
python pipeline/run_lgs.py \
  --goal /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/analysis_strict/output.goal \
  --L 4000 --G 0.04 --o 200 \
  --bin-cache-dir /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/bin_cache \
  --comm-dep-out /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/commdep_strict/comm_dep.csv
python pipeline/run_composite_lp.py \
  --goal /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/analysis_strict/output.goal \
  --comm-dep /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/commdep_strict/comm_dep.csv \
  --out /mnt/scratch/SC_Tracing_revalidation/vllm_llama70b_N2/composite_strict/composed_runtime.csv \
  --l-min 0 --l-max 8000 --step 4000 --l-intra 350 --o 200
```

This validates the online Llama70B N2 path, not the packaged vLLM8B paper curve under `data/output/vllm_llama8b_128tok/`.

For the guarded Fig. 5 NSYS pipeline:

```bash
bash pipeline/reproduce_fig5_from_nsys.sh --dry-run
bash pipeline/reproduce_fig5_from_nsys.sh --run-lp
```

The default URL is the online Llama7B N4/GPU16 one-iteration raw NSYS subtree:
`http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N4_GPU16_TP1_PP1_DP16_BS32_1iter/raw_nsys/`.
The `--run-lp` mode can take substantial time and requires Gurobi. On `bigmem`,
the local-NSYS run completed in 9m30s with 5.1 GiB peak RSS, but did not match
the packaged Fig. 5 Monolithic curve; see
`results/revalidation/fig5_from_nsys/summary.md`.

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

## Final Scratch Rerun Campaign

The strongest local validation bundle was produced on branch
`final_scratch_rerun_20260627` from existing GOAL files, NCCL metadata sidecars,
and NSYS/SQLite inputs. It avoids using packaged scientific CSVs as model
outputs, while still preserving large scratch artifacts outside git:

```bash
python3 scripts/final_scratch_rerun_campaign.py --workers 8
python3 scripts/summarize_final_scratch_rerun.py \
  --results-dir results/final_scratch_rerun_20260627
```

Key outputs:

- `results/final_scratch_rerun_20260627/final_scratch_summary.md`
- `results/final_scratch_rerun_20260627/comparison_summary.csv`
- `results/final_scratch_rerun_20260627/manual_lgs_summary.csv`
- `results/final_scratch_rerun_20260627/grok_node_scaling/`
- `new_results/final_scratch_rerun_20260627/`

The final Grok scaling plot uses fresh scratch outputs where available. At
`L=4000 ns`, N64 has hardware 9562.007 ms, Composite-LP 8604.782 ms, LGS
9788.116 ms, and Monolithic-LP 8072.785 ms. N64 Monolithic-LP is the largest
exact LP point attempted in this pass: 42.8M variables, 99.7M constraints,
5h11m45s wall time, and 133.4 GiB peak RSS. N128/N256 Monolithic-LP was not
launched.

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
- Real Monolithic-LP regeneration succeeded for Grok N4/GPU16, selected local Grok N8/N16/N32/N64 high-RAM points, and a local Llama7B N2/GPU8 trace when valid `comm_dep` sidecars were available or generated.
- Real NCCL metadata-sidecar Composite-LP regeneration succeeded for Grok through N512. Corrected row-nranks cold-cache runs are available for N64, N256, and N512; N4-N512 scaling plots use real metadata, not packaged-large rows.
- Grok N128 LogGOPSim was regenerated from the 16 GiB GOAL for the final scaling plot. The run used `--normalize-tags never` and a scratch txt2bin cache, completed in 1h20m13s, and replaced the previous invalid all-zero N128 LGS CSV in the plot inputs.
- Llama7B N32 Composite-LP latency and fixed-L bandwidth curves are regenerable from packaged V2 metadata sidecars; latency matches within 0.0276% max relative difference and bandwidth within 0.6335%.
- Online vLLM Llama70B N2 NSYS reports regenerate through NSYS export, V2 GOAL generation, LGS sidecar emission, and Composite-LP; Composite-LP matches LGS within about 0.186% on sampled points.
- The guarded Fig. 5 NSYS-to-GOAL-to-sidecar-to-Monolithic-LP path runs on the online/local Llama7B N4 one-iteration inputs, but the regenerated curve differs from the packaged Fig. 5 Monolithic curve by 120.64% max relative difference.
- LGS/LP numeric comparisons were saved under `results/revalidation/`.
- The remaining vLLM gap is the packaged vLLM8B paper curve: the available online raw trace is Llama70B N2 and does not numerically match `data/output/vllm_llama8b_128tok/`.
- The final scratch rerun results are under `results/final_scratch_rerun_20260627/` and `new_results/final_scratch_rerun_20260627/`. They include fresh-cache Grok Composite-LP through N512, complete manual N128 LGS, partial manual N256 LGS through `L=500000 ns`, and N64 Monolithic-LP at `L=4000 ns`.

See `docs/progress_log.md` for commands and `docs/revalidation_report.md` for the workload matrix and detailed sidecar analysis.
