# Figure End-to-End Validation Summary

Date: 2026-06-26

Repository: `/home/hpcuser/SC_Tracing`

Branch: `clean_version`

Scope: this pass distinguishes plot reproduction from data/model regeneration. `python3 reproduce_all.py` redraws paper figures from packaged CSVs. The runs below rerun model phases from existing GOAL or NCCL metadata sidecars, without recollecting traces.

## Summary Table

| Figure/workload | Regenerated phase | Inputs used | Command status | Comparison vs packaged CSV | Notes |
| --- | --- | --- | --- | --- | --- |
| Fig. 1/5/6 Llama7B N32 Composite latency | NCCL metadata to per-motif LP cache to composed latency curve | `data/workspaces/llama7b_n32_spcl_20260407/analysis/{collective_instances.csv,comm_ring_info.csv}` plus `data/npkit/` | Success, cold cache, 19m26s, 3,096,888 KiB max RSS | Max abs diff 263,211 ns; max rel diff 0.0276%; mean rel diff 0.0107% | Requires packaged-compatible `--nic-per-rank --node-map-mode rank-block --force-sequential`. |
| Fig. 1/6 Llama7B N32 Composite bandwidth | NCCL metadata to fixed-L exact-GOAL motif solves to composed bandwidth curve | `data/workspaces/llama7b_n32_spcl_20260407/analysis/{collective_instances.csv,comm_ring_info.csv}` plus `data/npkit/` | Success, cold cache, 31m22s, 2,095,924 KiB max RSS | Max abs diff 1,461,179 ns; max rel diff 0.6335%; mean rel diff 0.0588% over 20 bandwidth points | Uses `pipeline/run_nccl_bw_sensitivity.py` at `L=4000 ns`; residual drift is concentrated at the high-bandwidth asymptote. |
| Fig. 3 AllReduce 16N 128MiB 1ch | NCCL metadata to Composite-LP latency curve | `data/output/final_plots/data/ar_128m_16n_ch1` | Success, cold cache, 30.67s, 503,084 KiB max RSS | Max abs diff 1,437,864 ns; max rel diff 11.60%; mean rel diff 5.07% | Matches low-latency/baseline points, diverges at high synthetic latency. |
| Fig. 3 AllReduce 16N 128MiB auto | NCCL metadata to Composite-LP latency curve | `data/output/final_plots/data/ar_128m_16n_auto` | Success with `--program-rank 4`, cold cache, 22.85s, 568,260 KiB max RSS | Max abs diff 1,473,691 ns; max rel diff 33.78%; mean rel diff 9.72% | Packaged metadata has no rank 0 rows; only ranks 4 and 6 are present. |
| Fig. 4 mixed collectives | NCCL metadata to Composite-LP latency curve | `data/output/final_plots/data/mixed_16n_ch1` | Success, cold cache, 1m25s, 848,644 KiB max RSS | Max abs diff 17,965,522 ns; max rel diff 5.14%; mean rel diff 4.18% | Regenerates the latency Composite curve but does not reproduce it exactly. |
| Fig. 7 memory scaling | Plot script only | hardcoded measured/extrapolated memory table in `scripts/fig07_memory_scaling.py` | Replotted by `reproduce_all.py` | Not a data pipeline run | The figure encodes recorded values, not a runnable LP sweep. |
| Fig. 8/9 cluster/cost | Plot script only | hardcoded derived latency/bandwidth/cost arrays in `scripts/fig08_09_cluster_params_cost.py` | Replotted by `reproduce_all.py` | Not a data pipeline run | Analytic/cost visualization, not trace regeneration. |
| Fig. 10 jitter | Plot script only | hardcoded Grok N1024 Composition values in `scripts/fig10_jitter.py` | Replotted by `reproduce_all.py` | Not a data pipeline run | Uses two Composition points in the script; no upstream sweep rerun in this pass. |

## Commands

Packaged figure redraw only:

```bash
/usr/bin/time -v timeout 7200 python3 reproduce_all.py
```

Llama7B N32 packaged-compatible Composite rerun:

```bash
/usr/bin/time -v timeout 7200 .venv/bin/python pipeline/run_nccl_composite.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out data/revalidation/figures_end_to_end/llama7b_n32_composite_packaged_mode/comp/sweeps/composed_runtime.csv \
  --cache-dir data/revalidation/figures_end_to_end/llama7b_n32_composite_packaged_mode/collective_cache \
  --clear-cache --parallel-solve --max-workers 8 \
  --node-map-mode rank-block --force-sequential --nic-per-rank
```

Llama comparison:

```bash
python3 scripts/compare_csv.py \
  --expected data/workspaces/llama7b_n32_spcl_20260407/output/comp/sweeps/composed_runtime.csv \
  --actual data/revalidation/figures_end_to_end/llama7b_n32_composite_packaged_mode/comp/sweeps/composed_runtime.csv \
  --out-dir results/revalidation/figures_end_to_end \
  --label llama7b_n32_composite_packaged_mode_vs_packaged \
  --points actual
```

Llama fixed-L bandwidth rerun:

```bash
/usr/bin/time -v timeout 7200 python3 pipeline/run_nccl_bw_sensitivity.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out data/revalidation/figures_end_to_end/llama7b_n32_bw_full/bandwidth_sensitivity.csv \
  --cache-dir data/revalidation/figures_end_to_end/llama7b_n32_bw_full/fixed_l_cache \
  --clear-cache --fixed-l-ns 4000 \
  --min-bw-gbps 10 --max-bw-gbps 1600 --num-points 20 --spacing log \
  --max-workers 8 --node-map-mode rank-block --force-sequential --nic-per-rank
```

Llama bandwidth comparison:

```bash
python3 scripts/compare_csv.py \
  --expected data/workspaces/llama7b_n32_spcl_20260407/output/bw_sensitivity_l4us_composition_exact_goal/bandwidth_sensitivity.csv \
  --actual data/revalidation/figures_end_to_end/llama7b_n32_bw_full/bandwidth_sensitivity.csv \
  --out-dir results/revalidation/figures_end_to_end \
  --label llama7b_n32_bw_full_vs_packaged \
  --expected-x-col bw_gbps --actual-x-col bw_gbps \
  --expected-y-col runtime_ns --actual-y-col runtime_ns \
  --points actual
```

Fig. 3/4 Composite reruns use the same wrapper with `--analysis-dir` pointed at the corresponding `data/output/final_plots/data/*` directory. The exact commands and numeric summaries are recorded in `docs/progress_log.md` and `docs/revalidation_report.md`.

## Interpretation

The Llama7B N32 figure path is now a strong end-to-end validation from packaged metadata: the cold regenerated Composite curve matches the packaged curve within 0.0276% max relative difference. The critical historical setting was `--nic-per-rank`; without it, the same metadata solves a lower-cost motif family and underpredicts the packaged baseline by about 36%.

The Llama bandwidth curve now has an end-to-end metadata regeneration path. It is close but not bit-exact versus the packaged CSV; the max relative drift is 0.6335% and appears at the high-bandwidth asymptote. A compatibility probe with the old generator snapshot did not eliminate that drift, so exact reproduction likely requires the full historical driver/model environment.

The Fig. 3/4 microbenchmark Composite curves are regenerable from metadata, but not exact. The current cleaned wrapper produces valid curves and clean numeric comparisons, but the packaged microbenchmark CSVs appear to have been generated with slightly different historical modeling assumptions or incomplete metadata. LGS points and Monolithic-LP curves for these panels remain packaged-data reproduction only unless matching GOAL plus `comm_dep.csv` is provided.
