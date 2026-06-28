# Visual Check Bundle

This directory contains compact visual checks from the final scratch rerun.

## Layout

- `standalone/regenerated_curves/`: regenerated curve only.
- `standalone/paper_reference_curves/`: packaged paper/reference curve only.
- `side_by_side/`: reference curve beside regenerated curve with matched axes.
- `standalone/paper_figures/`: packaged paper figure redraws from `figures/`.
- `standalone/new_plots/`: requested new Grok node-scaling plots.

The side-by-side plots are generated from numeric comparison CSVs under `results/final_scratch_rerun_20260627/comparisons/`. For Grok comparison plots, the reference is the local development replay output rather than a paper PDF figure.

## Generated Comparisons

- `llama_n32_composite_vs_packaged`
- `llama_n32_bandwidth_vs_packaged`
- `fig03_ch1_vs_packaged`
- `fig03_auto_vs_packaged`
- `fig04_mixed_vs_packaged`
- `fig5_mono_vs_packaged`
- `fig5_historical_composite_vs_packaged`
- `fig5_historical_composite_vs_old_dev`
- `grok_N4_composite_vs_development`
- `grok_N8_composite_vs_development`
- `grok_N16_composite_vs_development`
- `grok_N32_composite_vs_development`
- `grok_N64_composite_vs_development`
- `grok_N256_composite_vs_development`
- `grok_N512_composite_vs_development`
- `grok_N128_lgs_vs_previous_regen`
- `grok_N256_lgs_vs_development_stats`

## Copied Paper Figure Redraws

- `standalone/paper_figures/fig_2d_sensitivity_workloads.png`
- `standalone/paper_figures/fig_2d_sensitivity_workloads.pdf`
- `standalone/paper_figures/fig_3x3_sensitivity.png`
- `standalone/paper_figures/fig_3x3_sensitivity.pdf`
- `standalone/paper_figures/fig3_sensitivity_1x4.png`
- `standalone/paper_figures/fig3_sensitivity_1x4.pdf`
- `standalone/paper_figures/fig3_sensitivity_2x2.png`
- `standalone/paper_figures/fig3_sensitivity_2x2.pdf`
- `standalone/paper_figures/fig_mixed_16n_ch1.png`
- `standalone/paper_figures/fig_mixed_16n_ch1.pdf`
- `standalone/paper_figures/fig5_llama7b.png`
- `standalone/paper_figures/fig5_llama7b.pdf`
- `standalone/paper_figures/fig6_grok_memory.png`
- `standalone/paper_figures/fig6_grok_memory.pdf`
- `standalone/paper_figures/fig_network_perf_combined.png`
- `standalone/paper_figures/fig_network_perf_combined.pdf`
- `standalone/paper_figures/fig_jitter_3panel.png`
- `standalone/paper_figures/fig_jitter_3panel.pdf`

## Copied New Plots

- `standalone/new_plots/grok_node_scaling_multi_latency.png`
- `standalone/new_plots/grok_node_scaling_multi_latency.pdf`
- `standalone/new_plots/grok_node_scaling_nominal_L0.png`
- `standalone/new_plots/grok_node_scaling_nominal_L0.pdf`
- `standalone/new_plots/grok_node_scaling_nominal_L4000.png`
- `standalone/new_plots/grok_node_scaling_nominal_L4000.pdf`
- `standalone/new_plots/grok_node_scaling_nominal_L250000.png`
- `standalone/new_plots/grok_node_scaling_nominal_L250000.pdf`
- `standalone/new_plots/grok_node_scaling_nominal_L500000.png`
- `standalone/new_plots/grok_node_scaling_nominal_L500000.pdf`
- `standalone/new_plots/grok_node_scaling_nominal_L1e+06.png`
- `standalone/new_plots/grok_node_scaling_nominal_L1e+06.pdf`
