# Packaged Figure Reproduction Summary

Date: 2026-06-26

Machine: `bigmem`

Branch: `clean_version`

Commit before this reproduction pass: `d92338b Add Grok N64 and N512 cold Composite validation`

## Commands

Packaged figures only:

```bash
/usr/bin/time -v timeout 7200 python3 reproduce_all.py
```

Result: success. Runtime was 22.22s wall clock with 193,900 KiB max RSS.

Pipeline demo plus packaged figures:

```bash
/usr/bin/time -v timeout 7200 python3 reproduce_all.py --pipeline
```

Result: success. Runtime was 22.34s wall clock with 191,352 KiB max RSS. The demo LogGOPSim sweep wrote `data/demo_output/lgs_points.csv`.

## Paper Figure Outputs

`reproduce_all.py` regenerated the scripted paper figures:

| Paper figure | Output |
| --- | --- |
| 1 | `figures/fig_2d_sensitivity_workloads.pdf` |
| 3 | `figures/fig3_sensitivity_1x4.pdf` |
| 4 | `figures/fig_mixed_16n_ch1.pdf` |
| 5 | `figures/fig5_llama7b.pdf` |
| 6 | `figures/fig_3x3_sensitivity.pdf` |
| 7 | `figures/fig6_grok_memory.pdf` |
| 8/9 | `figures/fig_network_perf_combined.pdf` |
| 10 | `figures/fig_jitter_3panel.pdf` |

The scripts also regenerate PNG versions and helper/detail plots under `figures/`.

## Manifests

- `figure_sha256.txt` records SHA256 checksums for all regenerated PDF/PNG files under `figures/`.
- `figure_sizes.csv` records file sizes for the same outputs.

No single packaged plot reproduction command approached the 2-hour limit.
