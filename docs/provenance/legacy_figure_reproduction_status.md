# Legacy figure reproduction status

Date: 2026-06-28

Repository: `/home/hpcuser/SC_Tracing`

Latest local validation branch: `final_scratch_rerun_20260627`

This document separates two different claims:

- Packaged redraw: `python3 reproduce_all.py` redraws the paper figure from CSVs and constants already shipped in the artifact.
- Data/model regeneration: the artifact reruns a nontrivial upstream phase, such as NCCL metadata to Composite-LP, GOAL to LogGOPSim, or GOAL plus `comm_dep.csv` to LP.

## Packaged Redraw

Command:

```bash
/usr/bin/time -v timeout 7200 python3 reproduce_all.py
```

Result: success in 22.22s wall time with 193,900 KiB max RSS. The packaged path regenerated figures 1, 3, 4, 5, 6, 7, 8/9, and 10 under `figures/`.

## Data-Level Status By Figure

| Figure | Packaged redraw | Data/model regeneration status | Numeric closeness |
| --- | --- | --- | --- |
| Fig. 1 sensitivity maps | Yes | Partial. Llama N32 latency and bandwidth inputs were regenerated from NCCL metadata in the final scratch pass; Grok 4096-GPU and vLLM8B panels remain packaged-output driven. | Final scratch: Llama latency max rel diff 0.118992%; Llama bandwidth max rel diff 0.639316%. Earlier best Llama latency compatibility run was 0.027530%. Grok 4096-GPU and vLLM8B packaged curves were not regenerated end-to-end. |
| Fig. 3 AllReduce microbenchmark | Yes | Composite-LP from packaged metadata works for 16-node 128MiB 1-channel and auto-channel cases. | Final scratch: 1-channel max rel diff 11.962891%; auto-channel max rel diff 17.601333%. Reproducible, but not numerically matching. |
| Fig. 4 mixed collectives | Yes | Composite-LP from packaged metadata works for the mixed 16-node case. | Final scratch max rel diff 5.094390%. Close in shape, not bit-exact. |
| Fig. 5 Llama7B iteration | Yes | Raw/SQLite to GOAL to `comm_dep.csv` to Monolithic-LP works on the current online/local N4 one-iteration trace. Metadata Composite-LP also works. Historical Composite mode reproduces the old development curve. | Final scratch: Monolithic vs packaged max rel diff 120.622541%; historical Composite vs old development max rel diff 0.063448%, but historical Composite vs packaged max rel diff 15.898682%. The shipped Fig. 5 high-latency slope is still not fully recovered. |
| Fig. 6 3x3 sensitivity grid | Yes | Partial. Llama N32 latency and bandwidth panels have end-to-end metadata regeneration. Grok 4096-GPU and vLLM8B panels remain packaged-output driven. | Same final scratch Llama inputs as Fig. 1: 0.118992% latency max rel diff and 0.639316% bandwidth max rel diff. Grok 4096-GPU and vLLM8B panel inputs were not regenerated end-to-end. |
| Fig. 7 memory scaling | Yes | Plot-only. The script encodes recorded/extrapolated memory values; no upstream LP sweep is rerun. | Reproduces from shipped constants. No independent numeric regeneration claim. |
| Fig. 8/9 cluster and cost | Yes | Plot-only. The script uses hardcoded derived latency, bandwidth, and cost arrays. | Reproduces from shipped constants. No independent numeric regeneration claim. |
| Fig. 10 jitter | Yes | Plot-only. The script uses two hardcoded Grok N1024 Composition values and interpolates jitter impact. | Reproduces from shipped constants. No upstream jitter sweep rerun. |

## Additional Grok Scaling Plot

The requested Grok node-count scaling plot is not one of the original paper figure scripts, but it now has stronger data-level evidence than the paper-scale Grok figures:

- Outputs: `new_results/final_scratch_rerun_20260627/` and `results/final_scratch_rerun_20260627/grok_node_scaling/`.
- Scope: N4, N8, N16, N32, N64, N128, N256, and N512.
- Methods included: hardware points, fresh scratch LGS where available, fresh scratch Composite-LP where available, multi-latency exact Monolithic-LP points through N64 where feasible, and the earlier N128 exact Monolithic-LP point at `L=4000 ns`.
- Fresh-cache Composite-LP in the final scratch pass matched development replay within 0.000151% for N64, 0.000599% for N256, and 0.000933% for N512.
- N128 LGS was regenerated completely. N256 LGS produced 5/6 requested latency points before the 6-hour timeout; the missing point is `L=1e6 ns`.
- N64 Monolithic-LP completed fresh points at `L=0`, `4000`, `10000`, `250000`, and `500000 ns`. The `L=1000000 ns` point was interrupted after no visible progress; the partial metadata marks it missing. The N64 model has 42.8M LP variables and 99.7M constraints.
- N128 Monolithic-LP completed one fresh `L=4000 ns` point: 7,137.090 ms, 80.6M LP variables, 200.8M constraints, 11h17m46s wall time, and 266.7 GiB peak RSS.

## Publishable Small Grok Artifact Guidance

Safe small files to publish or keep in the repo:

- `results/revalidation/grok_node_scaling/`
- `new_results/`
- Small CSV/JSON comparison summaries under `results/revalidation/grok_N*_composite_*`
- Provenance logs and command summaries in `docs/progress_log.md` and `docs/revalidation_report.md`

Files intentionally not included in a small publication bundle:

- Raw NSYS reports
- Full GOAL traces unless explicitly needed and size-checked
- Solver scratch directories and txt2bin caches
- Large LP sidecars such as `data/revalidation/grok_N64_commdep_lgs/comm_dep.csv`, currently about 494 MB
