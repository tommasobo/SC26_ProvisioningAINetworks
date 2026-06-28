# Final Scratch Rerun Summary

Repository: `/home/hpcuser/SC_Tracing`

Branch: `final_scratch_rerun_20260627`

Commit: `0a20c14ee8a54fd1a0ab3578acdf47b26a873e8a`

Results directory: `results/final_scratch_rerun_20260627`

Command used for the main campaign:

```bash
python3 scripts/final_scratch_rerun_campaign.py --workers 8
```

The campaign starts from existing GOAL, NCCL metadata sidecars, and NSYS/SQLite inputs. It deliberately writes fresh solver caches, `comm_dep.csv` files, LGS binary caches, and outputs under the scratch root instead of reusing packaged scientific CSVs as model results.

## Campaign Status

Tasks recorded: `51`.

Non-OK tasks: `5`.

| Task | Status | Return code | Elapsed s | Log |
| --- | --- | --- | --- | --- |
| fig5_nsys_to_monolithic | failed | 1 | 588.4 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig5_nsys_to_monolithic.log |
| grok_N128_composite_cold | timeout | 124 | 7200.0 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N128_composite_cold.log |
| compare_grok_N128_composite_vs_development | failed | 1 | 0.5 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N128_composite_vs_development.log |
| grok_N128_lgs_fresh | failed | 1 | 308.8 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N128_lgs_fresh.log |
| grok_N256_lgs_fresh | failed | 143 | 279.0 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N256_lgs_fresh.log |

## Key Task Timings

| Task | Status | Elapsed s | Max RSS GiB |
| --- | --- | --- | --- |
| packaged_reproduce_all | ok | 22.1 | 0.179 |
| demo_pipeline_reproduce_all | ok | 22.2 | 0.180 |
| pytest | ok | 7.8 | 0.206 |
| llama_n32_composite_cold | ok | 1221.8 | 2.638 |
| llama_n32_bandwidth_cold | ok | 1919.5 | 2.003 |
| fig5_nsys_to_monolithic | failed | 588.4 | 4.886 |
| vllm_regenerate_from_sqlite | ok | 867.9 | 1.588 |
| vllm_composite_lp | ok | 244.0 | 3.167 |
| grok_N64_composite_cold | ok | 2973.2 | 1.598 |
| grok_N128_composite_cold | timeout | 7200.0 | 0.126 |
| grok_N256_composite_cold | ok | 1869.1 | 8.008 |
| grok_N512_composite_cold | ok | 8914.0 | 30.487 |
| grok_N256_lgs_fresh | failed | 279.0 | 0.016 |
| grok_N64_monolithic_point_fresh | ok | 18705.2 | 133.391 |
| grok_node_scaling_plot_fresh_outputs | ok | 52.4 | 0.320 |

## Manual Patched LGS Reruns

These reruns were launched after fixing large temporary `txt2bin` output placement; they are outside the campaign manifest and are summarized from fresh CSV/log files.

| Task | Status | Rows | Min L ns | Max L ns | Elapsed | Max RSS GiB | CSV |
| --- | --- | --- | --- | --- | --- | --- | --- |
| manual_grok_N128_lgs_fresh_patched_tmp | complete | 6 | 0.0 | 1000000.0 | 1:36:38 | 50.037 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok/output/grok_n128/lgs/sweeps/lgs_runtime.csv |
| manual_grok_N256_lgs_fresh_patched_tmp | partial | 5 | 0.0 | 500000.0 | 6:00:00 | 191.947 | /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok/output/grok_n256/lgs/sweeps/lgs_runtime.csv |

## Numeric Comparisons

| Comparison | Points | Max abs diff ns | Max rel diff | Mean rel diff |
| --- | --- | --- | --- | --- |
| llama_n32_composite_vs_packaged | 201 | 1.35897e+06 | 0.118992% | 0.0469613% |
| llama_n32_bandwidth_vs_packaged | 20 | 1.46675e+06 | 0.639316% | 0.0631953% |
| fig03_ch1_vs_packaged | 201 | 1.50162e+06 | 11.9629% | 5.28428% |
| fig03_auto_vs_packaged | 201 | 1.37919e+06 | 17.6013% | 8.22098% |
| fig04_mixed_vs_packaged | 201 | 1.81807e+07 | 5.09439% | 4.17017% |
| fig5_mono_vs_packaged | 21 | 1.89979e+09 | 120.623% | 74.2% |
| fig5_historical_composite_vs_old_dev | 201 | 659849 | 0.0634482% | 0.0228275% |
| fig5_historical_composite_vs_packaged | 201 | 2.57621e+08 | 15.8987% | 10.0489% |
| grok_N128_lgs_vs_previous_regen | 6 | 2.81586e+07 | 0.301502% | 0.0952124% |
| grok_N16_composite_vs_development | 201 | 24831 | 0.000264613% | 0.000105116% |
| grok_N256_composite_vs_development | 201 | 44935.7 | 0.000599275% | 0.000447874% |
| grok_N256_lgs_vs_development_stats | 3 | 2.73553e+08 | 3.07542% | 2.40882% |
| grok_N32_composite_vs_development | 201 | 18830.4 | 0.000225747% | 0.000147122% |
| grok_N4_composite_vs_development | 201 | 6.35937e+08 | 9.47508% | 2.2065% |
| grok_N512_composite_vs_development | 201 | 70672 | 0.00093281% | 0.000573017% |
| grok_N64_composite_vs_development | 201 | 12941 | 0.000150477% | 0.000135747% |
| grok_N8_composite_vs_development | 201 | 24704 | 0.000502897% | 0.000239782% |

## Interpretation Notes

- `fig5_nsys_to_monolithic` can be non-OK even when GOAL, `comm_dep.csv`, and `full_runtime.csv` are generated; the wrapper exits nonzero when the regenerated curve differs from the shipped historical baseline beyond tolerance.
- Composite-LP tasks in this campaign use `--clear-cache` and write fresh solver caches under the scratch root.
- Large LGS runs use scratch-backed `--tmp-dir`/`--bin-cache-dir` paths so binary conversion does not exhaust `/tmp`.
- Large GOAL files, SQLite exports, binary caches, and LP sidecars remain under the scratch root; only compact summaries are written here.

## Grok Scaling Plot Outputs

- Repository plot directory: `results/final_scratch_rerun_20260627/grok_node_scaling`
- New-results mirror: `/home/hpcuser/SC_Tracing/new_results/final_scratch_rerun_20260627`
- Regenerate after long-running LGS/Monolithic jobs finish with:

```bash
python3 scripts/grok_node_scaling.py \
  --scratch-root /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok \
  --extra-scratch-root /mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/grok \
  --out-dir results/final_scratch_rerun_20260627/grok_node_scaling \
  --nodes 4 8 16 32 64 128 256 512 \
  --target-latency 0 \
  --target-latencies 0 4000 10000 250000 500000 1000000 \
  --no-packaged-large --include-legacy-monolithic
```

## Generated Files

- Task CSV: `results/final_scratch_rerun_20260627/task_summary.csv`
- Comparison CSV: `results/final_scratch_rerun_20260627/comparison_summary.csv`
- Manual LGS CSV: `results/final_scratch_rerun_20260627/manual_lgs_summary.csv`
- Manifest: `results/final_scratch_rerun_20260627/manifest.json`
- Campaign report: `results/final_scratch_rerun_20260627/report.md`
