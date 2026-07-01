# Fig. 5 NSYS-to-LP Revalidation

Input: local Llama7B N4/GPU16 one-iteration NSYS/SQLite workspace matching the online trace directory `http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N4_GPU16_TP1_PP1_DP16_BS32_1iter/raw_nsys/`.

Commands:

```bash
timeout 7200 bash pipeline/reproduce_fig5_from_nsys.sh \
  --skip-download \
  --work /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local \
  --run-lp

python3 pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/analysis \
  --out /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/composite_default/composed_runtime.csv \
  --cache-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/composite_default/cache \
  --clear-cache --parallel-solve --max-workers 8 \
  --l-min 0 --l-max 1000000 --step 5000

python3 pipeline/run_nccl_composite.py \
  --analysis-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/analysis \
  --out results/revalidation/fig5_from_nsys/composite_historical_mode/composed_runtime.csv \
  --cache-dir /mnt/scratch/SC_Tracing_revalidation/fig5_llama_n4_1iter_local/composite_nicperrank_20260627_103906/cache \
  --generator-dir /mnt/scratch/LLAMA/Traces_Compression/tools/nccl_generator_v2_hwfix \
  --npkit-simple /mnt/scratch/LLAMA/Traces_Compression/reference_bundle/npkit_results/simple_1ch/npkit_data_summary_Simple_alps.json \
  --npkit-ll /mnt/scratch/LLAMA/Traces_Compression/reference_bundle/npkit_results/ll_1ch/npkit_data_summary_LL_alps.json \
  --node-map-mode rank-block --ring-duplicate-policy last \
  --nic-per-rank --parallel-solve --max-workers 8 \
  --l-min 0 --l-max 1000000 --step 5000

python3 pipeline/run_lgs.py \
  --goal /mnt/scratch/LLAMA/Traces_Compression/workspaces/llama7b_n4_spcl_20260407/analysis/output.goal \
  --L 1000 --G 0.04 --o 200 \
  --comm-dep-out /mnt/scratch/SC_Tracing_revalidation/fig5_old_goal_mono_control/comm_dep.csv

python3 pipeline/run_monolithic_lp.py \
  --goal /mnt/scratch/LLAMA/Traces_Compression/workspaces/llama7b_n4_spcl_20260407/analysis/output.goal \
  --comm-dep /mnt/scratch/SC_Tracing_revalidation/fig5_old_goal_mono_control/comm_dep.csv \
  --out /mnt/scratch/SC_Tracing_revalidation/fig5_old_goal_mono_control/full_runtime.csv \
  --l-min 0 --l-max 1000000 --step 50000 \
  --l-intra 350 --o 200 --G 0.04
```

Results:

| Path | Runtime | Max RSS | Comparison |
| --- | ---: | ---: | --- |
| NSYS SQLite -> GOAL/metadata | 59.1s | included in helper run | generated 244 MiB `output.goal` and NCCL metadata sidecars |
| GOAL -> `comm_dep.csv` via patched LogGOPSim | 133.42s | included in helper run | generated 16 MiB LP sidecar |
| Monolithic-LP full sweep | 376.5s | 5,123,260 KiB | vs packaged `partial_100pct/full_runtime.csv`: max rel 120.638%, mean rel 74.217% |
| Composite-LP default | 16.30s | 351,440 KiB | vs packaged `comp_100pct/composed_runtime.csv`: max rel 23.787%, mean rel 20.620% |
| Composite-LP force-sequential | 2.27s warm cache | 89,712 KiB | vs packaged Composite: max rel 22.565%, mean rel 19.707% |
| Composite-LP historical mode | 2.27s warm cache | 90,272 KiB | vs old development curve: max rel 0.063642%, mean rel 0.018858%; vs packaged Composite: max rel 15.953%, mean rel 10.069% |
| Historical GOAL -> `comm_dep.csv` via patched LogGOPSim | 33.27s | not separately recorded | generated 891,270 LP sidecar rows from the old 311 MiB GOAL |
| Historical GOAL Monolithic-LP control | 423.4s | 5,661,144 KiB | vs regenerated-GOAL Monolithic: max rel 1.668%, mean rel 1.177%; vs packaged `partial_100pct/full_runtime.csv`: max rel 124.319%, mean rel 76.730% |

Root-cause notes:

- The current online/local raw NSYS files and the local one-iteration analysis sidecars match for `collective_instances.csv`, `comm_info.csv`, `comm_ring_info.csv`, `comm_tree_info.csv`, and `profiling_interval.csv`; only `output.goal` and `goal_label_ranges.csv` differ between historical and regenerated GOAL emission.
- The historical GOAL is larger than the regenerated GOAL, 311 MiB vs 255 MiB, but this is not the main Monolithic mismatch. Running Monolithic-LP on the historical GOAL with a freshly emitted historical `comm_dep.csv` produces a curve within 1.668% max relative difference of the regenerated-GOAL Monolithic curve, while still differing from the packaged Fig. 5 Monolithic CSV by 124.319% max relative difference.
- The old development Composite path used `nic_per_rank=True` inside motif LPs. The cleaned wrapper defaults to the current LPConverter NIC model, so `--nic-per-rank` is required for historical Llama comparisons.
- The trace has three stream IDs but no overlapping collective intervals on rank 0 (`stream_overlap_ns=0`, `max_active_collectives=1`). The wrapper now uses parallel stream composition only when intervals actually overlap. With `--nic-per-rank` and automatic no-overlap sequential composition, it reproduces the old development curve within 0.064% max relative difference.
- The shipped packaged Fig. 5 Composite CSV still has a steeper high-latency slope than the reproduced old development curve. At `L=0`, historical mode gives 841.387 ms and packaged Composite gives 841.780 ms; at `L=1e6`, historical mode gives 1361.894 ms and packaged Composite gives 1620.392 ms. This remaining difference is not explained by `comm_dep` sidecars or by the current public one-iteration NSYS input alone.
- The shipped `partial_100pct/sweeps/full_runtime.csv` and `partial_100pct/sweeps/compressed_runtime.csv` are numerically identical to floating-point roundoff, with maximum absolute difference `7.4e-6 ns` over 201 points. They differ strongly from both true Monolithic-LP controls, whose endpoint at `L=1e6 ns` is about 3.48-3.53 s rather than the shipped 1.575 s.
- A local search over `/mnt/scratch` and `/home/hpcuser` found exact matches for the shipped Fig. 5 CSVs only inside clones of this artifact repository. The recovered development workspace contains the lower-slope Composite curve, not the shipped Fig. 5 Composite CSV.

Interpretation: the Fig. 5 raw/SQLite path is runnable end-to-end on a moderate N4 trace, including LP sidecar emission and Gurobi solve. The old development Composite curve is now reproducible from the same metadata using documented historical switches. The exact shipped Fig. 5 CSV is not fully reproduced because its Monolithic and Composite curves appear to come from an unrecovered historical model/input or postprocessing path, not from the recovered old development workspace or from the current public one-iteration NSYS inputs.
