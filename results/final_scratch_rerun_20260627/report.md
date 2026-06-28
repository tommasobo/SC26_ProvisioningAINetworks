# Final Scratch Rerun Report

Updated UTC: `2026-06-28T02:09:58Z`

Branch: `final_scratch_rerun_20260627`

Commit: `0a20c14ee8a54fd1a0ab3578acdf47b26a873e8a`

Scratch root: `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627`

## Task Status

| Task | Status | Elapsed s | Max RSS GiB | Log |
| --- | --- | ---: | ---: | --- |
| `packaged_reproduce_all` | `ok` | 22.1 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/packaged_reproduce_all.log` |
| `demo_pipeline_reproduce_all` | `ok` | 22.2 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/demo_pipeline_reproduce_all.log` |
| `pytest` | `ok` | 7.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/pytest.log` |
| `llama_n32_composite_cold` | `ok` | 1221.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/llama_n32_composite_cold.log` |
| `compare_llama_n32_composite_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_llama_n32_composite_vs_packaged.log` |
| `llama_n32_bandwidth_cold` | `ok` | 1919.5 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/llama_n32_bandwidth_cold.log` |
| `compare_llama_n32_bandwidth_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_llama_n32_bandwidth_vs_packaged.log` |
| `fig03_ch1_composite_cold` | `ok` | 23.7 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig03_ch1_composite_cold.log` |
| `compare_fig03_ch1_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig03_ch1_vs_packaged.log` |
| `fig03_auto_composite_cold` | `ok` | 24.1 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig03_auto_composite_cold.log` |
| `compare_fig03_auto_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig03_auto_vs_packaged.log` |
| `fig04_mixed_composite_cold` | `ok` | 67.6 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig04_mixed_composite_cold.log` |
| `compare_fig04_mixed_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig04_mixed_vs_packaged.log` |
| `fig5_nsys_to_monolithic` | `failed` | 588.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig5_nsys_to_monolithic.log` |
| `compare_fig5_mono_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig5_mono_vs_packaged.log` |
| `fig5_composite_historical_cold` | `ok` | 15.7 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/fig5_composite_historical_cold.log` |
| `compare_fig5_historical_composite_vs_old_dev` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig5_historical_composite_vs_old_dev.log` |
| `compare_fig5_historical_composite_vs_packaged` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_fig5_historical_composite_vs_packaged.log` |
| `vllm_nsys_export_nsys_report_nid006673_57756` | `ok` | 21.1 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/vllm_nsys_export_nsys_report_nid006673_57756.log` |
| `vllm_nsys_export_nsys_report_nid006679_8937` | `ok` | 20.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/vllm_nsys_export_nsys_report_nid006679_8937.log` |
| `vllm_regenerate_from_sqlite` | `ok` | 867.9 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/vllm_regenerate_from_sqlite.log` |
| `vllm_composite_lp` | `ok` | 244.0 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/vllm_composite_lp.log` |
| `grok_N4_composite_cold` | `ok` | 4.7 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N4_composite_cold.log` |
| `compare_grok_N4_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N4_composite_vs_development.log` |
| `grok_N8_composite_cold` | `ok` | 9.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N8_composite_cold.log` |
| `compare_grok_N8_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N8_composite_vs_development.log` |
| `grok_N16_composite_cold` | `ok` | 41.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N16_composite_cold.log` |
| `compare_grok_N16_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N16_composite_vs_development.log` |
| `grok_N32_composite_cold` | `ok` | 359.3 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N32_composite_cold.log` |
| `compare_grok_N32_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N32_composite_vs_development.log` |
| `grok_N64_composite_cold` | `ok` | 2973.2 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N64_composite_cold.log` |
| `compare_grok_N64_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N64_composite_vs_development.log` |
| `grok_N128_composite_cold` | `timeout` | 7200.0 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N128_composite_cold.log` |
| `compare_grok_N128_composite_vs_development` | `failed` | 0.5 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N128_composite_vs_development.log` |
| `grok_N256_composite_cold` | `ok` | 1869.1 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N256_composite_cold.log` |
| `compare_grok_N256_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N256_composite_vs_development.log` |
| `grok_N512_composite_cold` | `ok` | 8914.0 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N512_composite_cold.log` |
| `compare_grok_N512_composite_vs_development` | `ok` | 0.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/compare_grok_N512_composite_vs_development.log` |
| `grok_N4_lgs_fresh` | `ok` | 50.7 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N4_lgs_fresh.log` |
| `grok_N8_lgs_fresh` | `ok` | 46.1 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N8_lgs_fresh.log` |
| `grok_N16_lgs_fresh` | `ok` | 164.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N16_lgs_fresh.log` |
| `grok_N32_lgs_fresh` | `ok` | 1039.3 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N32_lgs_fresh.log` |
| `grok_N64_lgs_fresh` | `ok` | 3253.2 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N64_lgs_fresh.log` |
| `grok_N128_lgs_fresh` | `failed` | 308.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N128_lgs_fresh.log` |
| `grok_N256_lgs_fresh` | `failed` | 279.0 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N256_lgs_fresh.log` |
| `grok_N4_monolithic_point_fresh` | `ok` | 218.8 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N4_monolithic_point_fresh.log` |
| `grok_N8_monolithic_point_fresh` | `ok` | 243.0 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N8_monolithic_point_fresh.log` |
| `grok_N16_monolithic_point_fresh` | `ok` | 561.2 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N16_monolithic_point_fresh.log` |
| `grok_N32_monolithic_point_fresh` | `ok` | 2600.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N32_monolithic_point_fresh.log` |
| `grok_N64_monolithic_point_fresh` | `ok` | 18705.2 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_N64_monolithic_point_fresh.log` |
| `grok_node_scaling_plot_fresh_outputs` | `ok` | 52.4 |  | `/mnt/scratch/SC_Tracing_final_scratch_rerun_20260627/logs/grok_node_scaling_plot_fresh_outputs.log` |

## Notes

- Commands use fresh cache/output directories under the scratch root.
- Large sidecars, txt2bin caches, and solver caches are not copied into the repo.
- Small comparison JSON/CSV summaries are under `comparisons/`.
