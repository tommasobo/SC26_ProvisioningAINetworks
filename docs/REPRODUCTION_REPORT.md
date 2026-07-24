# Final reproduction report

Date: 24 July 2026

Branch: `artifact_freeze`

The final branch is based on `local_artifact` at `081c8f3`. The three handoffs
form a linear history:

```text
eabd898 final_scratch_rerun_20260627
  -> cdba247 alps-reproduction-20260724
    -> 081c8f3 local_artifact
```

No merge was needed. The final branch adds the clean quick and full entry
points, Slurm jobs, the closest cross-branch results, the combined AD/AE, and
this report.

## Summary

| Figure | Final status | Best quantitative match | Data used for the final plot |
| --- | --- | --- | --- |
| 1 | Plot reproduced | Exact redraw of compact data | Existing Llama, Grok 4k, and vLLM data |
| 3 | Closely reproduced from raw traces | Ch1 latency 0.0783%; auto latency 0.1661%; ch1 bandwidth 2.3730%; auto bandwidth 1.4934% maximum relative error | Existing paper CSVs for the paper-style plot; fresh raw-derived CSVs retained separately |
| 4 | Closely reproduced from raw traces | Latency 0.1418%; bandwidth 0.2420% maximum relative error | Existing paper CSV for the paper-style plot; fresh raw-derived CSVs retained separately |
| 5 | Closest recovered curve selected | Composite 0.014853% maximum and 0.004879% mean relative error over 201 points | Recovered raw-derived Composite result; existing Monolithic and LGS data |
| 6, Llama | Closely reproduced from metadata | Archived latency 0.02753%; July one-queue bandwidth 0.35796%; final four-queue bandwidth 0.57081% maximum relative error | Existing compact curves; metadata and bounded full rerun are provided |
| 6, vLLM | Exact raw replay at the archived job point; full paper curve remains different | Full curve differs by 13.83% for latency and 20.32% for bandwidth | Existing paper curve in the paper-style plot; exact raw replay evidence retained |
| 6, Grok 4k | Plot reproduced only | No new expensive run | Existing CSVs |
| 7 | Plot reproduced | Exact redraw of compact memory data | Existing data |
| 8 and 9 | Plot reproduced only | Exact redraw of published values | Compact sweep and network-cost inputs |
| 10 | Plot reproduced | Exact redraw of compact jitter data | Existing data |

All percentages compare result CSVs with the compact CSV used by the paper
plot. They are not pixel comparisons.

## Figure 1

Figure 1 is reproduced with `scripts/fig01_sensitivity_maps.py`. It uses the
existing one-dimensional latency and bandwidth sweeps and constructs the
published additive phase map. It is not a joint two-dimensional simulation.

The Llama N32 inputs are the same metadata-derived curves used in Figure 6.
The Grok 4,096-GPU and vLLM inputs are existing CSVs. No expensive experiment
was rerun.

## Figure 3

The July Alps work started from the recovered 64-report NSYS campaigns for the
one-channel and automatic-channel 128 MiB AllReduce cases. It regenerated
SQLite, GOAL, NCCL metadata, communication dependencies, LGS outputs, and LP
outputs.

The best automatic-channel configuration came from the historical generator
with four physical NICs per node. The best latency result uses the historical
four-NIC GOAL and the paper-era non-serialized LP convention. The best
bandwidth result additionally enables one NIC queue per rank with four
physical queues per node. This combination is more accurate than the earlier
`local_artifact` result:

| Panel | Points | Maximum relative error | Mean relative error |
| --- | ---: | ---: | ---: |
| One channel, latency | 6 | 0.078265% | 0.025093% |
| Auto channels, latency | 6 | 0.166084% | 0.056438% |
| One channel, bandwidth | 61 | 2.373021% | 0.229570% |
| Auto channels, bandwidth | 61 | 1.493366% | 0.522520% |

The selected CSVs are under `results/reproduced/fig3/`. The full plotting
script retains the paper curves for the overlaid Monolithic and Composite
lines, as in the submitted figure. The fresh results are kept as separate
evidence so paper-reference inputs remain immutable.

The compact-metadata Composite task in the full script is a diagnostic, not
the selected Figure 3 result. Its final Slurm run differs by 11.87% for one
channel and 17.83% for automatic channels. Rank selection, metadata versus
rank-block topology, first versus last duplicate rings, stream composition,
intra-node transfers, and one versus four NIC queues were tested. The compact
metadata do not retain enough of the paper campaign to recover the raw-trace
Monolithic curves, which is why the selected raw-derived CSVs are reported
separately.

## Figure 4

The closest curve comes from the older job 1808340 campaign. Starting from its
64 NSYS reports, the local handoff regenerated all 201 latency points and 61
bandwidth points:

| Panel | Maximum relative error | Mean relative error |
| --- | ---: | ---: |
| Latency | 0.141781% | 0.047379% |
| Bandwidth | 0.242013% | 0.040058% |

The matching campaign contains AllGather sizes from 0.5 to 4 MiB and AllReduce
sizes from 32 to 256 MiB. This conflicts with the paper text that says all
messages were 16 to 64 MiB. The corrected job 1791883 follows the written
range but does not reproduce the paper curve. Both alternatives were tested.
The most likely issue is a paper text or campaign-selection mismatch, not a
solver failure.

The fresh compact-metadata Composite diagnostic differs by 5.06%. Topology,
ring, sequencing, and NIC alternatives were tested. The raw-trace
Monolithic-LP campaign above remains the closest reproducible result.

## Figure 5

All three branches and both scratch campaigns were compared. The closest
result is:

```text
local_artifact/results/fig5/composed_runtime.csv
```

It differs from the paper Composite CSV by at most 0.0148527% and by 0.0048791%
on average over 201 points. The endpoints are 841.7994 and 1620.4152 ms,
compared with 841.7802 and 1620.3919 ms in the paper CSV. The final slope is
identical.

Other available configurations were investigated before selecting this curve:

- current/default and force-sequential Composite runs differ by 23.79% and
  22.57%;
- historical metadata compatibility runs differ by about 15.90%;
- force-parallel streams differs by about 16.55%;
- an exact cold run with the preserved `5d1ce52` solver source differs by
  about 23.74%;
- a fresh Monolithic run differs by 120.62%;
- the historical GOAL Monolithic control differs by 124.32%;
- the public V2 static BIN is a different 2.1 to 3.3 second program.

The raw reports, regenerated and historical sidecars, GOAL emission, stream
overlap, node maps, ring policy, and exposed NIC/intra-node switches were
checked. They do not explain the remaining provenance gap.

The selected result is documented as a raw-derived existing result, not as a
new cold reproduction. Its four NSYS hashes and result hash are committed.
The exact paper-era per-motif transformation or cache that produced the close
curve was not included in the handoff. This is the remaining Figure 5 gap.

The current paper labels this workload Llama 8B. The observed trace identifies
Llama 7B, N4/GPU16/DP16/BS32, one iteration, with 202 collectives. The
difference is treated as a model-version label issue.

## Figure 6

### Llama

The bounded full workflow regenerates the Llama N32 Composite latency and
bandwidth curves from committed NCCL metadata. The final configuration is:

```text
--node-map-mode rank-block --force-sequential \
--nic-per-rank --nics-per-node 4
```

The closest archived June cold run predates the explicit multi-NIC option. It
differs by 0.02753% for latency and 0.63347% for bandwidth, with runtimes of 19
minutes 26 seconds and 31 minutes 22 seconds. The July current-source
single-queue alternative differs by 0.12766% for latency and 0.35796% for
bandwidth.

The one-queue bandwidth run was repeated from a fresh cache on the final
branch. It differs by 0.91627% maximum and 0.05389% mean. Most points agree
closely with the July result; the drift is concentrated at 937.8 and
1224.9 Gbps, where the run-to-run differences are 0.422% and 0.869%.
Because the committed code, inputs, and configuration are identical, this is
most likely solver variation among nearly equivalent motif-LP solutions. Both
CSVs are committed.

Restoring the four physical Alps injection queues gives 0.09510% latency and
0.57081% bandwidth error on the final branch. The full workflow uses this
configuration because it matches the physical topology and is the closer
fresh final-branch bandwidth result.

The archived comparison tables remain committed so the paper-era match is not
lost. The metadata identify Llama 7B at N32/GPU128/DP128, while the paper
label says Llama 70B. The evidence supports a paper label mismatch.

### vLLM

The exact Llama-3.1-8B N2/GPU8, 128-token NSYS input was recovered from local
job 1812656. It was freshly exported and converted through SQLite, GOAL, BIN,
LogGOPSim, and plotting. The replay matches the archived job runtime exactly
at the recorded latency point.

The resulting full sensitivity curves differ from the paper by 13.83% for
latency and 20.32% for bandwidth. The available online 70B trace was also
tested and is not a valid substitute. The likely missing item is the
paper-era token-window or iteration-reduction transformation.

### Grok

The 4,096-GPU panels use existing CSVs. The full launcher supports a cold
metadata run only behind `--expensive_run` and an explicit N1024 analysis
directory. The historical latency solve took about 4.4 hours. It was not run
for this freeze.

The complete optional latency and bandwidth analysis should be treated as a
multi-day workload. We recommend a large-memory node with at least 512 GB of
RAM and approximately 3 to 5 days of wall time, depending on solver
parallelism.

## Figure 7

`scripts/fig07_memory_scaling.py` redraws the memory-scaling result from the
committed compact table. No large-memory LP experiment was rerun during this
freeze.

## Figures 8 and 9

`scripts/fig08_09_cluster_params_cost.py` redraws the two-panel network
parameter sensitivity plot and the separate network-cost plot from the
compact latency, bandwidth, and cost inputs. Figure 8 includes both the Llama
and Grok panels. The two outputs retain the paper's column widths and aspect
ratios.

## Figure 10

`scripts/fig10_jitter.py` redraws the jitter result from the committed compact
table. No stochastic jitter experiment was rerun during this freeze.

## Plotting caveats

The paper-style plotting scripts intentionally preserve several properties of
the submitted figures:

- Figure 3 draws the same packaged paper curve for the overlapping
  Monolithic and Composite lines.
- Figure 4 draws the same packaged paper curve for the overlapping
  Monolithic and Composite lines.
- Figure 6 uses real packaged LGS data for Llama latency, but several other
  sparse LGS marker series are derived from the paper Composite curves.
- Figure 6 replaces the first five Grok bandwidth points with the published
  values used by the paper.
- The vLLM measured marker comes from the compact paper input.

These choices reproduce the paper presentation. The fresh validation CSVs are
kept separately and are not silently substituted for paper-reference data.

## Existing data versus reruns

| Item | Treatment in this freeze |
| --- | --- |
| Figures 1, 7, 8, 9, and 10 | Existing data, plotting rerun |
| Figure 3 | Existing paper data for plotting; prior raw NSYS rerun consolidated; selected results rechecked |
| Figure 4 | Existing paper data for plotting; prior raw NSYS rerun consolidated; selected results rechecked |
| Figure 5 Composite | Closest existing raw-derived result selected after cross-branch investigation |
| Figure 5 Monolithic and LGS | Existing data |
| Figure 6 Llama | Existing data for plotting; metadata-level cold rerun supported and validated |
| Figure 6 vLLM | Existing paper data for plotting; prior exact raw replay consolidated |
| Figure 6 Grok 4k | Existing data only; no new expensive run |

The quick plot path completed in under 20 seconds on Alps. The final Slurm
validation used separate jobs for the core checks, demo, Figures 3 to 5, and
the two configured Figure 6 sweeps, followed by one extra one-queue bandwidth
alternative. Gurobi-limited Figure 6 jobs are serialized by the final launcher
so they do not exceed the available concurrent license slots.

The final validation jobs completed as follows:

| Task | Slurm job | Elapsed | Result |
| --- | ---: | ---: | --- |
| Core checks | 2892657 | 00:00:36 | Passed |
| LogGOPSim demo | 2892688 | 00:00:12 | Passed |
| Figure 3 diagnostic | 2892827 | 00:00:41 | Passed |
| Figure 4 diagnostic | 2892828 | 00:00:43 | Passed |
| Figure 5 comparison | 2892661 | 00:00:11 | Passed |
| Figure 6 latency, four queues | 2892662 | 00:18:57 | 0.09510% maximum error |
| Figure 6 bandwidth, four queues | 2892734 | 00:27:42 | 0.57081% maximum error |
| Figure 6 bandwidth, one-queue repeat | 2892826 | 00:29:05 | 0.91627% maximum error |

An initial demo job exposed missing build tools in the compute-node
environment and a paper-era LogGOPSim argument incompatibility. The final
demo task builds only when the optional tools are available and omits the
new default topology argument for old binaries. An initial concurrent Figure
6 bandwidth submission exceeded the available Gurobi WLS slots. The final
launcher serializes the two Figure 6 jobs. These failed probes are not part of
the table above.

## AD/AE

The final combined AD/AE is in `docs/ad/ad_ae_appendix.tex` and
`docs/ad/ad_ae_appendix.pdf`. It follows the official SC26 structure, includes
both artifacts, documents the quick, full, Slurm, and expensive paths, and
states the limitations above. No DOI, release, or archive was created.
