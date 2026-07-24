# Alps reproduction notes for SC26 Figures 3–6

This document records the CSCS/Alps reproduction performed on 22–24 July
2026 for the paper *Provisioning Networks for AI Supercomputers: A
Trace-Driven Study of Performance Sensitivity at Unprecedented Scale*.
Grok was excluded. The machine-readable results are in
`numeric_summary.json` in the reproduction output directory.

The most important distinction is:

- The paper plots can be redrawn from the CSVs already committed under
  `data/` by running `reproduce_all.py`. This is a packaged-data redraw, not
  an independent validation.
- The strong Figure 3 and Figure 4 checks below started again from recovered
  original `.nsys-rep` files. Those large files are not committed to this
  repository. They currently live in the CSCS run directory documented
  below.
- Figure 6 Llama can be regenerated from metadata committed to the
  repository, but that is a metadata-level regeneration rather than a raw
  NSYS regeneration.
- Stock LLAMP is now shown wherever a packaged CSV is present (Figures 3,
  4, and 5). These gray dashed curves are parsed from committed CSVs and
  explicitly labelled `Stock LLAMP (packaged CSV)`; they are not claimed as
  fresh stock-LLAMP executions.
- The exact Figure 5 paper input and Figure 6 vLLM 8B input are still
  missing. The repository alone cannot independently reproduce those panels.

## Pinned checkout and output

- SC_Tracing checkout:
  `/iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722/SC_Tracing`
- SC_Tracing baseline commit:
  `eabd898dee8ac53eab4ccc334674fe1e71e64a89`
  (`final_scratch_rerun_20260627`)
- Historical evidence commit:
  `Traces_Compression@87a1ab6c`
  (`origin/codex-analytical-formula-comparison`)
- Run root:
  `/iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722`
- Output:
  `/iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722/reproduction_clariden-ln004_20260722T013845`
- Python environment: `SC_Tracing/.venv-repro`
- Nsight Systems used for export: 2025.1.1
- Alps topology used in the models: four ranks/GPUs per node,
  `L_intra=350 ns`, `G_intra=0.00333 ns/byte`, `o=200 ns`.

The historical commit is important because it contains the original GH200
multi-NIC convention: four physical NIC/injection queues per node, one per
GPU, with NCCL CPU/channel lanes mapped by `cpu % nics_per_node`. Restoring
that convention was necessary for the Figure 3 automatic-channel result.

## Input data

| Panel | Input actually used | Count / size | Classification and caveat |
| --- | --- | ---: | --- |
| Fig. 3, 1 channel | `inputs/fig3/n16_n32_traces/allreduce_128m_16n_ch1/nsys_reports/` under the run root | 64 NSYS; 672,830,278 B | Exact recovered raw campaign: 128 MiB Ring/Simple AllReduce, 16 nodes, 64 ranks, forced one channel |
| Fig. 3, auto | `inputs/fig3/n16_n32_traces/allreduce_128m_16n_auto/nsys_reports/` | 64 NSYS; 495,339,543 B | Exact recovered raw campaign: same workload, automatic/eight channels |
| Fig. 4, job 1808340 | `inputs/fig4/curve_source_job1808340/n16_n32_traces/mixed_16n_ch1/nsys_reports/` | 64 NSYS; 64,599,444 B | Likely published-curve source and the numerical match, but its 0.5–256 MiB message set conflicts with the paper text |
| Fig. 4, job 1791883 | `inputs/fig4/corrected_job1791883/.../mixed20_rand16to64_16n_ch1_job1791883/trace/nsys_reports/` | 64 NSYS; 64,713,505 B | Corrected campaign matching the written 20-collective/16–64 MiB/seed 20262014 configuration; it does not match the paper curve |
| Fig. 5 | historical `llama7b_n4` metadata sidecars plus `/iopsstor/scratch/cscs/btommaso/orderedchaos_ae/inputs/llama7b_n4/llama.bin` | BIN 241,872,936 B | Related Llama 7B inputs only. Neither is the proven paper input; paper says 8B |
| Fig. 6 Llama | `data/workspaces/llama7b_n32_spcl_20260407/analysis/` | packaged metadata, 128 ranks | Derived metadata only. It identifies Llama 7B N32/GPU128/DP128, while the paper says 70B |
| Fig. 6 vLLM | none | — | Exact Llama-3.1-8B N2/GPU8/128-token input expired; not reproduced and no 70B substitute was used |
| Stock LLAMP overlays | committed `*_stock_runtime.csv` files listed below | 7 CSVs; 987 data rows | Derived/packaged solver outputs only. Parsed for plot context, not regenerated from original inputs |

Source-container hashes:

```text
7641ae2cc151f6ce0d998e447d3e429f2a6820b5c42fc2b94962aafe85036eb3  /users/btommaso/all_traces.zip
66ccd40d1783b18bd789ece355cdecc4ca3a64a16fbd5ded46557f3f6a5ac9e9  /users/btommaso/mixed20_atlahs_rerun_results_20260403_annotated_rerun.zip
d69bd1bda72ed9e5b2794fdf9070aaec63f388e3a863c70af0b9fd41c37e6604  /iopsstor/scratch/cscs/btommaso/orderedchaos_ae/inputs/llama7b_n4/llama.bin
```

The Figure 4 corrected bundle also contains
`goal/InterNode_MicroEvents_Dependency.goal` and
`goal/mixed20_rand16to64_16n_ch1.bin`. The GOAL begins with
`num_ranks 16`, contradicting the 64 NSYS reports and the 64-rank manifest.
It was tested as provenance evidence but was not called an exact 64-rank
input.

Job 1808340 is an end-to-end downstream reproduction, not a redraw of its
packaged runtime CSV: its 64 recovered NSYS reports were freshly exported to
SQLite, converted to a new GOAL and metadata set, replayed through LGS, used
to regenerate `comm_dep.csv`, and freshly solved through Monolithic and
Composite LP. The packaged Figure 4 CSV appears only as the dashed comparison
curve. This distinction is why job 1808340 is the primary Figure 4 panel in
the side-by-side PDF even though its message sizes conflict with the written
paper configuration.

## Process used

### 1. Export raw NSYS reports

The original reports were never modified. Each report was exported to a new
SQLite file on scratch:

```bash
cd /iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722
sbatch export_target_nsys.sbatch
```

The job ran `nsys export --type=sqlite` in parallel and created 256 SQLite
files totaling 4,389,945,344 bytes. These SQLite files are derived and must
not be used as replacements for the original NSYS reports.

### 2. Regenerate GOAL and NCCL metadata

```bash
sbatch regenerate_metadata.sbatch
```

For each campaign this called:

```bash
SC_Tracing/.venv-repro/bin/python \
  SC_Tracing/pipeline/run_nccl_generator.py \
  --sqlite-dir <fresh-sqlite-directory> \
  --out-dir <new-analysis-directory>
```

The generator creates `output.goal`, `collective_instances.csv`,
`comm_ring_info.csv`, and related sidecars. The July validation patches make
SQLite traversal and rank assignment deterministic and preserve four
contiguous GPU ranks per node.

For Figure 3 auto, the GOAL was regenerated with the recovered historical
topology:

```bash
sbatch run_historical_multinic_fig3_auto.sbatch
```

The decisive generator option is `--nics-per-node 4`.

### 3. Run LGS and create communication dependencies

Text GOAL was converted with `txt2bin` and replayed with the freshly built
LogGOPSim. The latency sweep used:

```text
G_inter = 0.04 ns/byte
L = 0 ... 1,000,000 ns
o = 200 ns
g = 5 ns
ranks_per_node = 4
L_intra = 350 ns
G_intra = 0.00333 ns/byte
```

Commands are preserved in:

- `../run_lgs_topology_corrected.sbatch`
- `../run_historical_multinic_fig3_auto.sbatch`
- `../run_fig3_lgs_bandwidth.sbatch`

Patched LogGOPSim also emitted `comm_dep.csv`, which disambiguates matched
send/receive operations for the Monolithic LP. A cached CSV or plot was never
used as a substitute for this dependency reconstruction.

### 4. Run Monolithic and Composite LP

Selected latency points were solved with:

```bash
python pipeline/run_monolithic_points.py \
  --goal <fresh-output.goal> \
  --comm-dep <fresh-comm_dep.csv> \
  --out <new-output.csv> \
  --latencies 0 200000 400000 600000 800000 1000000 \
  --ranks-per-node 4 --l-intra 350 --g-intra 0.00333 \
  --o 200 --G 0.04
```

All 61 Figure 3 bandwidth points (`G=0,0.002,...,0.12 ns/byte`) were solved
with `pipeline/run_monolithic_bandwidth_points.py`. The automatic-channel
bandwidth run used `--nic-per-rank --nics-per-node 4`. Exact commands are in:

- `../run_fig3_monolithic_bandwidth.sbatch`
- `../run_fig3_auto_monolithic_4nic.sbatch`
- `../run_lgs_monolithic.sbatch`

The metadata-based Composite path was independently run with
`pipeline/run_nccl_composite.py`; see `../run_composite_models.sbatch` and
`../run_fig3_composite_4nic.sbatch`. Its remaining mismatch is reported
instead of being hidden. The closest scientific match for Figure 3 is the
fresh Monolithic/raw-GOAL path.

The unusually large corrected Figure 4 LP did not yield a first point after
about 38 minutes with the normal dual-simplex path. It subsequently completed
all six points with optimal status using the parallel-barrier fallback
documented in `../run_fig4_corrected_barrier.sbatch`.

### 5. Figure 5 and Figure 6

Figure 5's historical metadata was cold-solved with:

```bash
sbatch ../run_fig5_historical_metadata.sbatch
```

It reproduces an older development curve within 0.059%, but not the packaged
paper slope. The public-V2 `llama.bin` was replayed separately through LGS
and produced a different 2.1–3.3 second program. These are negative
provenance results, not successful paper reproductions.

Figure 6 Llama was regenerated from the repository's metadata using:

```bash
python pipeline/run_nccl_composite.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out <new-latency-output.csv> \
  --cache-dir <new-cache> --clear-cache \
  --node-map-mode rank-block --force-sequential --nic-per-rank

python pipeline/run_nccl_bw_sensitivity.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out <new-bandwidth-output.csv> \
  --cache-dir <new-cache> --clear-cache \
  --fixed-l-ns 4000 --min-bw-gbps 10 --max-bw-gbps 1600 \
  --num-points 20 --spacing log \
  --node-map-mode rank-block --force-sequential --nic-per-rank
```

This is fully regenerable from repository data, but remains a
metadata-level check with a 7B/70B identity conflict.

### 6. Parse the packaged stock-LLAMP CSVs

The side-by-side presentation parses the following committed files directly
with `pandas.read_csv`:

| Figure | CSV | Rows | SHA-256 |
| --- | --- | ---: | --- |
| 3 ch1 latency | `data/output/final_plots/data/ar_128m_16n_ch1/latency_stock_runtime.csv` | 201 | `27ca9a8efc941ce0868fca8b3c3790876a2d506e0ee1585190ac2b645739b494` |
| 3 ch1 bandwidth | `data/output/final_plots/data/ar_128m_16n_ch1/bw_stock_runtime.csv` | 61 | `504546c55c7dce68a6c44a06ae3303ea460e726b450496bdca8d0078c5cb2363` |
| 3 auto latency | `data/output/final_plots/data/ar_128m_16n_auto/latency_stock_runtime.csv` | 201 | `fdaf4184465ab2258fb77356338260c872fcb19e8d462635816d4fece377b74a` |
| 3 auto bandwidth | `data/output/final_plots/data/ar_128m_16n_auto/bw_stock_runtime.csv` | 61 | `108e57096f9fa1bb23476ba2266d996f793e8621383351f5e4a1f7f8a8f12b76` |
| 4 latency | `data/output/final_plots/data/mixed_16n_ch1/latency_stock_runtime.csv` | 201 | `5310b3f0551b7649330794720cf53337ea1ac4484428865192fd90195d5cafa0` |
| 4 bandwidth (retained, not needed by the current Figure 4 page) | `data/output/final_plots/data/mixed_16n_ch1/bw_stock_runtime.csv` | 61 | `569b11fb47d64bcd95b4ac0ea36d16fc5225b010e26bad0673147a4e4aef292b` |
| 5 latency | `data/output/llama7b/partial_100pct/sweeps/stock_runtime.csv` | 201 | `fa352e764dabc83ec72cc4c14c2e1fee2ce7c067cb212fc09e383f1ee7208ff7` |

Latency CSVs use `L` in nanoseconds and `runtime` in nanoseconds; the plot
converts them to microseconds and milliseconds. Bandwidth CSVs use `G` in
nanoseconds per byte and `runtime` in nanoseconds; the plot converts
`G > 0` to `BW = 8/G` Gbps and runtime to milliseconds. The Figure 4 page
contains only a latency panel, so its packaged bandwidth CSV is documented
but not plotted. No stock-LLAMP CSV exists for Figure 6.

These curves have zero parsing/redraw difference from their own source CSVs
by construction. That is not an accuracy measurement and must not be
reported as a successful stock-LLAMP reproduction. Restoring and validating
the original stock-LLAMP executable path remains future work.

### 7. Error calculation

Fresh points were compared to the packaged paper/reference CSVs with
`scripts/compare_csv.py`. For an actual point `x`, the paper curve is linearly
interpolated at `x`, then:

```text
absolute relative error (%) =
    100 * abs(T_fresh(x) - T_paper(x)) / abs(T_paper(x))
```

Both maximum and arithmetic mean absolute relative errors are reported.
Bandwidth LGS is compared against `bw_lgs_runtime.csv`; Monolithic is compared
against the packaged LP curve (`bw_composite_runtime.csv`, which the paper
plot uses for both Monolithic and Composite).

## Error versus the paper data

| Panel / method | Points | Max absolute relative error | Mean absolute relative error |
| --- | ---: | ---: | ---: |
| Fig. 3 ch1 latency, Monolithic | 6 | 0.078% | 0.025% |
| Fig. 3 ch1 latency, LGS | 21 | 5.256% | 0.646% |
| Fig. 3 ch1 bandwidth, Monolithic | 61 | 2.373% | 0.230% |
| Fig. 3 ch1 bandwidth, LGS | 61 | 9.028% | 1.783% |
| Fig. 3 auto latency, Monolithic | 6 | 0.166% | 0.056% |
| Fig. 3 auto latency, LGS | 21 | 2.285% | 0.548% |
| Fig. 3 auto bandwidth, Monolithic | 61 | 1.493% | 0.523% |
| Fig. 3 auto bandwidth, LGS | 61 | 23.192% | 3.735% |
| Fig. 4 job 1808340, Monolithic | 6 | 0.118% | 0.060% |
| Fig. 4 job 1808340, LGS | 21 | 2.076% | 0.612% |
| Fig. 4 job 1808340, Composite | 201 | 4.579% | 3.764% |
| Fig. 4 corrected job 1791883, Monolithic | 6 | 306.871% | 248.451% |
| Fig. 5 historical metadata, Composite | 201 | 15.910% | 10.038% |
| Fig. 5 public-V2 static BIN, LGS | 9 | 140.516% | 134.801% |
| Fig. 6 Llama metadata, latency | 201 | 0.128% | 0.057% |
| Fig. 6 Llama metadata, bandwidth | 20 | 0.358% | 0.026% |

Interpretation:

- Figure 3 is substantially reproduced from exact raw inputs. The strongest
  evidence is the Monolithic match, with LGS providing an independent check.
- Figure 4's plotted curve is numerically reproduced by job 1808340, but that
  campaign conflicts with the paper's stated message-size range. The
  corrected written-configuration job 1791883 is not the plotted curve.
- Figure 5 is not reproduced.
- Figure 6 Llama is a strong metadata-level match, not a raw-input match.
- Figure 6 vLLM is not reproduced.

## Hardware points and lower sensitivity panels

The comparison PDF now includes the same lower panels as the paper:

```text
lambda_L = dT / dL
mu_G     = dT / dG, with G = 8 / bandwidth
```

The derivatives on the right-hand side are computed from fresh curves, not
copied from the paper. Figure 3 bandwidth `mu_G` is shown in MB; Figure 6
Llama bandwidth uses GB, matching the paper conventions.

The red Alps star is reference hardware data taken from the packaged paper
metadata and is deliberately not described as a fresh solver result. It is
placed at 4 µs for latency and 200 Gbps for bandwidth. Values used:

| Panel | HW mean | Min–max | Packaged source |
| --- | ---: | ---: | --- |
| Fig. 3 ch1 | 11.493953 ms | 11.084672–11.950496 ms | `data/output/final_plots/data/ar_128m_16n_ch1/collective_instances.csv` |
| Fig. 3 auto | 4.648064 ms | 4.647936–4.648192 ms | `data/output/final_plots/data/ar_128m_16n_auto/collective_instances.csv` |
| Fig. 4 | 188.992507 ms | 188.662656–189.286653 ms | `data/output/final_plots/data/mixed_16n_ch1/collective_instances.csv` |
| Fig. 5 | 895.65 ms | single packaged value | `scripts/fig05_llama_iteration.py` |
| Fig. 6 Llama | 1.100909 s | 1.070591–1.104504 s | `data/workspaces/llama7b_n32_spcl_20260407/analysis/collective_instances.csv` |

For Figure 3 the duration is the first collective per packaged goal rank. For
Figures 4 and 6 it is the full interval from the first start to the final end
per rank. Error bars span the packaged minimum and maximum.

## Regeneration commands

### Redraw the paper figures from repository CSVs

This is cheap and uses no raw traces:

```bash
cd /iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722/SC_Tracing
.venv-repro/bin/python reproduce_all.py --only 3 4 5 6
```

Outputs appear under `figures/`. Again, this demonstrates that the plotting
artifact is self-contained; it does not independently validate the
underlying simulations.

### Rebuild the side-by-side presentation

After the fresh outputs exist:

```bash
RUN_ROOT=/iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722
REPO=$RUN_ROOT/SC_Tracing
OUT_ROOT=$(<"$RUN_ROOT/CURRENT_OUTPUT_DIR")

"$REPO/.venv-repro/bin/python" \
  "$REPO/scripts/make_side_by_side_report.py" \
  --repo "$REPO" --out-dir "$OUT_ROOT" --host clariden-ln004 \
  --target "$REPO/figures/SC26_paper_vs_reproduction_clariden-ln004.pdf"
```

The output is:

```text
figures/SC26_paper_vs_reproduction_clariden-ln004.pdf
```

The PDF has paper/reference plots on the left and fresh results on the right.
Gray dashed paper-reference and Stock LLAMP curves, plus red hardware stars,
come from packaged paper data and are marked as context. Solid/marker
reproduction curves and their lower-panel derivatives are freshly generated.

## Verification

After the final code changes:

```bash
.venv-repro/bin/python -m pytest -q
.venv-repro/bin/python scripts/check_artifact.py --skip-figure
```

Result: `13 passed`; artifact check passed.

The full file-level provenance and hashes are in:

```text
/iopsstor/scratch/cscs/btommaso/sc26_reproduction_20260722/
  reproduction_clariden-ln004_20260722T013845/run_manifest.csv
```
