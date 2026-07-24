# Local reproduction handoff for SC26 AD/AE

> This is a preserved handoff, not the final user guide. Use the repository
> `README.md` and `docs/REPRODUCTION_REPORT.md` for the frozen workflow. A
> later cross-branch audit confirmed the Figure 5 result as the closest
> recovered curve, but also found that its exact cold Composite runner or
> paper-era per-motif cache was not committed. The four-NIC Figure 6 commands
> must include `--nics-per-node 4`.

This document is the detailed handoff for the local-PC reproduction of
Figures 3, 4, 5, and the non-Grok panels of Figure 6 from *Provisioning
Networks for AI Supercomputers: A Trace-Driven Study of Performance
Sensitivity at Unprecedented Scale*. It records what was actually rerun,
which inputs were used, exact configurations and hashes, what only started
from packaged metadata, and what still prevents a fully clean AE rerun.

The most important correction relative to earlier server-side notes is:

> The exact Figure 6 vLLM Llama-3.1-8B, N2/GPU8/TP8, 128-token NSYS input
> **does exist locally**. It is job `1812656` inside
> `vllm_recent_runs_20260407.zip`. The two reports were freshly exported,
> converted to an exact-size GOAL/BIN, and replayed to the exact runtime
> recorded by GOAL job `1812658`. The public Llama-3.1-70B trace was not used
> as a substitute.

## Branch and baseline

- Repository: `https://github.com/tommasobo/SC_Tracing.git`
- Handoff branch: `local_artifact`
- Branch base: `origin/alps-reproduction-20260724` at
  `cdba247213bf307fcd5d3a50778438f98ec856e5` (short form `cdba247`)
- That branch descends from the requested baseline
  `final_scratch_rerun_20260627` at
  `eabd898dee8ac53eab4ccc334674fe1e71e64a89`.
- On 2026-07-24, neither `final_AE` nor a pre-existing `local_artifact`
  branch was advertised by the GitHub remote. The next agent should merge or
  rebase this handoff into the eventual `final_AE` branch rather than assume
  that `local_artifact` is the final AE branch.
- The branch was prepared in an isolated Git worktree. The original dirty
  `Traces_Compression` and `SC_Tracing` checkouts were not cleaned or reset.

Local audit environment:

- Host/environment identifier: `laptop-cjl91217-wsl2`
- OS: Ubuntu 20.04.6 LTS under WSL2
- User: `tbonato`
- Audit dates: 2026-07-22 through 2026-07-24
- Nsight Systems exporter: `2025.4.1.172-254136343571v0`
- Main local source repository:
  `/home/tbonato/LLAMP_Test`
- Detailed local audit root:
  `/home/tbonato/LLAMP_Test/SC26_e2e_slides_laptop-cjl91217-wsl2_20260723T182036+0200`

Absolute paths are provenance for this machine. Portable commands below use
variables and scratch output directories.

## What is committed in this handoff

The `local_artifact/` directory contains:

- `figures/SC26_paper_vs_reproduced_figures_3_to_6.pdf`: four-page
  paper-above/reproduction-below report.
- `figures/figure6_reproduced.pdf`: enlarged non-Grok Figure 6 comparison.
- `results/reproduction_metrics.json`: pointwise error summary.
- `results/fig3/`, `results/fig4/`, `results/fig5/`, and
  `results/fig6/vllm/`: the small fresh solver/simulator CSVs.
- `manifests/vllm_figure6_files.csv`: exact vLLM archive/member hashes and
  all important derived-file hashes.
- `manifests/llama_figure6_public_nsys.csv`: all 32 public Llama N32 report
  names, exact HTTP content lengths, HTTP modification times, ETags, and
  URLs.
- `manifests/llama_figure6_local_metadata.csv`: hashes of the packaged
  metadata and comparison evidence actually used locally.
- `manifests/figure5_llama_n4_nsys.csv`: hashes of the four Figure 5
  Llama7B reports.
- `source_snapshots/atlahs_c7b8a457/inter_node_dependency.py`: the exact
  patched generator source present when the vLLM GOAL was regenerated.
- `scripts/`: snapshots of the small local sweep drivers. They are evidence
  of the exact calls used; the monolithic snapshots expect the historical
  `Traces_Compression@5d1ce52f` solver tree described below.
- `verify_manifests.py`: read-only verification of the committed metadata
  and, when supplied, the large local vLLM archive.

No NSYS, SQLite, large GOAL, large BIN, model weights, prompt files, or
private logs are committed. The branch contains identities and hashes for
those inputs, not the large files themselves.

## Result summary

Errors are pointwise comparisons against the CSV used by the paper plot.
They are not comparisons against pixels in the PDF.

| Panel | Starting point of fresh run | Best result | Status |
| --- | --- | ---: | --- |
| Fig. 3 latency, one channel | 64 exact NSYS | 0.813501% max relative error | Raw-to-plot, near-exact |
| Fig. 3 latency, auto/eight channels | 64 exact NSYS | 2.573770% max | Raw-to-plot, close |
| Fig. 3 bandwidth, one channel | Same exact NSYS/GOAL | 3.711248% max | Raw-to-plot, close |
| Fig. 3 bandwidth, auto/eight channels | Same exact NSYS/GOAL | 25.819773% max | Raw chain proven; paper-era bandwidth-model detail missing |
| Fig. 4 latency | 64 NSYS from the older plotted campaign | 0.141781% max, 0.047379% mean | Raw-to-plot, near-exact |
| Fig. 4 bandwidth cross-check | Same fresh GOAL | 0.242013% max | Raw-to-plot, near-exact |
| Fig. 5 Composite | 4 exact observed Llama7B NSYS | 0.014853% max | Raw-to-metadata-to-historical-Composite-to-plot |
| Fig. 5 Monolithic at L=0 | Same trace-derived model | 0.000265% | Exact checkpoint; full L=1 ms solve timed out |
| Fig. 6 Llama latency | Packaged trace-derived metadata | 0.027530% max | Metadata-to-cold-Composite-to-plot |
| Fig. 6 Llama bandwidth | Packaged trace-derived metadata | 0.633475% max | Metadata-to-cold-Composite-to-plot |
| Fig. 6 vLLM | 2 exact local NSYS | Exact archived job runtime at L=3.7 us; paper curve differs by 13.83–20.32% | Raw-to-GOAL-to-BIN-to-LGS proven; paper-specific reduction step missing |

## Figure 3: 128 MiB Ring/Simple AllReduce

### Exact input

The local input directories are:

```text
/home/tbonato/LLAMP_Test/data/raw/n16_n32_traces/allreduce_128m_16n_ch1/nsys_reports
/home/tbonato/LLAMP_Test/data/raw/n16_n32_traces/allreduce_128m_16n_auto/nsys_reports
```

Configuration:

- 16 nodes
- 64 GPUs/ranks
- 4 ranks per node
- 128 MiB Ring/Simple AllReduce
- one forced NCCL channel for `ch1`
- automatic/eight channels for `auto`

The one-channel set contains 64 NSYS reports totaling `672,830,278` bytes.
The auto set contains 64 reports totaling `495,339,543` bytes. Their
historical path provenance is also recorded by
`Traces_Compression@87a1ab6c` under
`data/raw/n16_n32_traces/allreduce_128m_16n_{ch1,auto}`.

### Pipeline used

1. Export all 128 NSYS reports with Nsight Systems 2025.4.1 into new SQLite
   databases. The fresh SQLite totals were `2,324,742,144` bytes for ch1
   and `1,709,297,664` bytes for auto.
2. Run the preserved April-5 NCCL generator at
   `workspaces/bandwidth_analysis/nccl_generator_v2_hwfix/main.py`.
   Its SHA-256 was
   `a167df0ccc6425e5f5b622faf3d1abf4ffdce3a821d396ce903633d5013e33f2`.
3. Compare the six core generated metadata CSVs with the historical
   workspace; all were byte-identical.
4. Run the preserved monolithic solver snapshot at
   `Traces_Compression@5d1ce52f9efb975749ee78a301db5379dc6081c6`.
5. Use the historically compatible node-contiguous mapping
   `node = rank // 4`. A rank/node map inferred from current report hostnames
   made the paper match materially worse; it is therefore retained as a
   diagnostic, not used for the displayed comparison.

Model parameters:

```text
ranks_per_node = 4
L_intra         = 350 ns
G_intra         = 0.00333 ns/byte
G_inter         = 0.04 ns/byte       # latency sweep
o               = 200 ns
barriers        = false
bandwidth L     = 5000 ns
bandwidth G     = 0.000 ... 0.120 ns/byte in 0.002 steps
```

Fresh GOAL identities:

```text
ch1   3,965,395 bytes  SHA-256 94ad2e37faae336e233c9dee0f5430876be277720673dd700c594f8451a8ad5a
auto  8,690,277 bytes  SHA-256 2ccddc13c34e39b3d9db78099225ecc7df75d33951ba215a4f5f02a6946373fe
```

The latency LPs contained 40,452 variables / 88,896 constraints for ch1 and
40,964 variables / 145,856 constraints for auto. See
`local_artifact/scripts/run_monolithic_snapshot.py` and
`local_artifact/scripts/run_bw_snapshot.py`.

The auto-channel bandwidth discrepancy is not an input-identity failure:
the same raw reports produce the close latency curve. The most likely
remaining item is the exact paper-era multi-NIC/channel assumption in the
bandwidth/compositional invocation.

## Figure 4: Mixed20

### Which campaign produced the plotted curve

The numerical match comes from the older campaign:

```text
/home/tbonato/LLAMP_Test/data/raw/n16_n32_traces/mixed_16n_ch1/nsys_reports
```

It contains 64 NSYS reports totaling `64,599,444` bytes. The regenerated
metadata contains 20 collective instances and 64 participant rows per
instance.

Important scientific caveat: this older plotted campaign does **not** match
the paper prose's “all messages 16–64 MiB” description. Its observed sizes
are:

```text
AllGather: 0.5 MiB, 1 MiB, 4 MiB
AllReduce: 32 MiB, 64 MiB, 128 MiB, 256 MiB
```

The corrected job `1791883`, seed `20262014`, is the campaign matching the
written 16–64 MiB intent, but it does not generate the paper curve. These
campaigns must remain separate in the AD/AE.

### Pipeline and best configuration

1. Freshly export all 64 NSYS reports to SQLite (`157,237,248` bytes total).
2. Regenerate metadata and a `67,359,064`-byte GOAL.
3. Verify the six core metadata CSVs byte-for-byte against the historical
   `output/all_traces/mixed_16n_ch1/generated` directory.
4. Run the preserved `5d1ce52f` monolithic solver with inter-collective
   barriers enabled.

The fresh GOAL SHA-256 is
`07e4aeec4c626a8a7990db82693d0a8280b9917b4faea2185ca309023b5bf2fc`.
The barrier-aware model has 617,607 variables and 1,381,792 constraints.
It produced the 201-point latency sweep in 443.65 seconds and the 61-point
bandwidth sweep in 236.67 seconds.

## Figure 5: Llama N4/GPU16/DP16

The exact reports used locally are listed with sizes and hashes in
`local_artifact/manifests/figure5_llama_n4_nsys.csv`. They are:

```text
nsys_report_nid007657_153302.nsys-rep
nsys_report_nid007660_285413.nsys-rep
nsys_report_nid007661_196350.nsys-rep
nsys_report_nid007662_294007.nsys-rep
```

Public source:

```text
http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N4_GPU16_TP1_PP1_DP16_BS32_1iter/raw_nsys/
```

Observed identity is Llama 7B/approximately 6.74B parameters, four nodes,
16 GPUs, DP16, one iteration, 202 collective instances. Paper versions and
captions have referred to this panel as 8B or 70B. The numerical near-match
supports a model-label typo; it does not turn the 7B trace into an 8B/70B
trace.

Pipeline:

1. Fresh NSYS 2025.4.1 export.
2. Fresh NCCL metadata/GOAL generation; five solver-facing metadata CSVs
   were byte-identical to the canonical workspace.
3. Preserved April-5 per-motif LP code, including recovered dependency
   metadata.
4. Sequential composition of the 12 unique collective models into the
   201-point curve.

The Composite curve's maximum relative difference is `0.0148527419%`.
The preserved-code Monolithic L=0 result is `847,598,851.228 ns`, versus
`847,596,608.228 ns` in the packaged curve (`0.0002646306%`). The full
Monolithic instance has about 2,285,940 variables and 5,015,836 constraints.
A direct L=1 ms solve reached the 1,345-second limit. A final large-memory
acceptance run should use incremental 5-us warm starts rather than jumping
directly from L=0 to L=1 ms.

## Figure 6 Llama panel

### Identity and what the local reproduction actually used

The input identifies itself as:

```text
Llama 7B
N32 / GPU128
PP1 / DP128
BS128
```

The paper panel says Llama 70B, N32/GPU128. No genuine Llama70B N32/GPU128
alternative was found. The public Llama70B dataset is N64/GPU256 and is a
different scale. Because the Llama7B metadata reproduces the numerical
curve very closely, the 70B label is treated as a paper-label typo.

The local run on which the comparison PDF is based starts from the packaged
trace-derived metadata already committed in this repository:

```text
data/workspaces/llama7b_n32_spcl_20260407/analysis/collective_instances.csv
data/workspaces/llama7b_n32_spcl_20260407/analysis/comm_ring_info.csv
data/workspaces/llama7b_n32_spcl_20260407/analysis/comm_info.csv
```

It did **not** freshly export the N32 NSYS reports on the laptop. Therefore
the correct claim is metadata-to-plot, not raw-NSYS-to-plot.

Metadata facts:

- 128 participant ranks
- 148 collective instances
- 18,944 participant rows (`148 x 128`)
- 10,240 ring/channel topology rows
- 8 unique supported collective signatures in the compositional solver

The exact committed hashes are in
`local_artifact/manifests/llama_figure6_local_metadata.csv`.

### Commands used for the cold metadata rerun

Latency:

```bash
python3 pipeline/run_nccl_composite.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out /mnt/scratch/SC_Tracing_local_artifact/llama_n32/latency/composed_runtime.csv \
  --cache-dir /mnt/scratch/SC_Tracing_local_artifact/llama_n32/latency/cache \
  --clear-cache --parallel-solve --max-workers 8 \
  --node-map-mode rank-block --force-sequential --nic-per-rank
```

Bandwidth:

```bash
python3 pipeline/run_nccl_bw_sensitivity.py \
  --analysis-dir data/workspaces/llama7b_n32_spcl_20260407/analysis \
  --out /mnt/scratch/SC_Tracing_local_artifact/llama_n32/bandwidth/bandwidth_sensitivity.csv \
  --cache-dir /mnt/scratch/SC_Tracing_local_artifact/llama_n32/bandwidth/cache \
  --clear-cache \
  --fixed-l-ns 4000 \
  --min-bw-gbps 10 --max-bw-gbps 1600 --num-points 20 --spacing log \
  --max-workers 8 \
  --node-map-mode rank-block --force-sequential --nic-per-rank
```

The best compatibility rerun differs from the packaged curve by at most
`0.02753006849%` for latency and `0.63347481134%` for bandwidth.

### Public original/static inputs

The matching public directory is:

```text
http://storage2.spcl.ethz.ch/traces/ai/llama/Llama7B_N32_GPU128_PP1_DP128_7B_BS128/
```

As checked on 2026-07-24, it exposes:

```text
llama.goal  7,803,465,561 bytes
llama.bin   4,818,127,926 bytes
nsys_reports/ containing 32 reports totaling 1,732,200,457 bytes
```

All 32 report names, exact HTTP content lengths, ETags, and URLs are in
`local_artifact/manifests/llama_figure6_public_nsys.csv`. SHA-256 is marked
`not_computed` because the 1.61 GiB NSYS set was not downloaded merely to
write this handoff. ETags are HTTP validators, not cryptographic hashes.

For a strict raw-to-plot AE claim, download those 32 reports to scratch,
compute SHA-256 locally, export them with a pinned Nsight Systems version,
regenerate the metadata, and compare it bytewise with the committed sidecars
before running the commands above. Do not place the 12.6 GB public GOAL+BIN
pair or the NSYS reports in Git.

## Figure 6 vLLM panel: exact local raw trace

### Why job 1812656 is the exact target

The paper/artifact label is vLLM inference with Llama-3.1-8B on eight GPUs
and the output folder is `vllm_llama8b_128tok`. The local archive contains:

| Trace job | Model | Nodes/GPUs | Max tokens | Use |
| --- | --- | --- | ---: | --- |
| 1812655 | Llama-3.1-8B-Instruct | N2/GPU8 | 32 | Related, wrong token count |
| **1812656** | **Llama-3.1-8B-Instruct** | **N2/GPU8** | **128** | **Exact target** |
| 1812657 | Llama-3.1-70B-Instruct | N2/GPU8 | 32 | Wrong model and token count |
| 1812749 | Llama-3.1-8B-Instruct | N2/GPU8 | 512 | Related, wrong token count |

Target run details:

```text
Archive:       /home/tbonato/LLAMP_Test/data/raw/vllm_recent_runs_20260407.zip
Archive SHA:   99555a2c4121ac63a8ca30ef90d30f793064c892fd62d54ccabe9a228c12eb48
Archive size:  1,168,072,301 bytes; 49 members
Run dir:       /iopsstor/scratch/cscs/btommaso/vllm_external_8b_hb128_1812656
Trace job:     1812656
GOAL job:      1812658
Model:         Llama-3.1-8B-Instruct
HF snapshot:   0e9e39f249a16976918f6564b8830bc894c89659
vLLM:          0.8.5
Nodes/GPUs:    2 nodes, 4 GPUs/ranks per node, 8 GPUs total
Parallelism:   tensor parallel 8, pipeline parallel 1
Prompts:       prompts_highbatch.txt, 64 prompts
Generation:    max tokens 128, temperature 0.6, top-p 0.95, bfloat16
Batch limits:  max_num_seqs=64, max_num_batched_tokens=32768
Model limit:   max_model_len=4096
GPU memory:    utilization=0.9
```

The prompt contents are not needed for the trace-to-GOAL replay and are not
committed. The sanitized launcher configuration above comes from the exact
archived `trace_1812656.out`.

The original trace collection command, with site paths replaced by
descriptive variables, was:

```bash
nsys profile \
  --trace=nvtx,cuda \
  --trace-fork-before-exec=true \
  --cuda-memory-usage=false \
  --force-overwrite=true \
  --cuda-um-cpu-page-faults=false \
  --cuda-um-gpu-page-faults=false \
  -s none \
  --output="$RUN_DIR/traces/nsys_report_%h_%p.nsys-rep" \
  python3 -m torch.distributed.run \
    --nproc_per_node 4 \
    --nnodes 2 \
    --rdzv_id 1812656 \
    --rdzv_backend c10d \
    --rdzv_endpoint nid007360:12656 \
    "$VLLM_INFERENCE_SCRIPT" \
    --model "$HF_CACHE/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659" \
    --tokenizer "$HF_CACHE/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659" \
    --distributed-executor-backend external_launcher \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 1 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9 \
    --prompt-file "$PROMPT_DIR/prompts_highbatch.txt" \
    --max-tokens 128 \
    --temperature 0.6 \
    --top-p 0.95 \
    --max-num-batched-tokens 32768 \
    --max-num-seqs 64 \
    --dtype bfloat16
```

### Exact NSYS reports

```text
vllm_recent_runs_20260407/vllm_external_8b_hb128_1812656/nsys/
  nsys_report_nid007360_28381.nsys-rep
    134,130,136 bytes
    SHA-256 db61a8f42b8d182ecb1f0f7fa554ddbc1a610919ebd7d02847f7f211ec0f0181
  nsys_report_nid007365_17404.nsys-rep
    133,559,747 bytes
    SHA-256 73b7a8b5290b7d10f471add21982b00c6babab7cf68f9b3320e5b821f6ef8e3f
```

There is one NSYS report per node; each report contains the four local
worker ranks/GPUs. The complete file-level manifest is
`local_artifact/manifests/vllm_figure6_files.csv`.

The public vLLM index currently exposes the DeepSeek V3.1 and
Llama-3.1-70B N2/GPU8 traces, not this exact 8B archive. Do not use
`Llama_3.1_70B_Instruct_N2_GPU8_TP8_Short_Prompts` as a substitute.

### Raw NSYS to fresh GOAL/BIN

Use a new scratch directory:

```bash
export VLLM_ARCHIVE=/path/to/vllm_recent_runs_20260407.zip
export VLLM_WORK=/mnt/scratch/SC_Tracing_local_artifact/vllm_8b_128tok
export NSYS_BIN=/path/to/nsight-systems-2025.4.1/bin/nsys
export ATLAHS=/path/to/atlahs

mkdir -p "$VLLM_WORK"/{archive,sqlite,goal,lgs}
unzip "$VLLM_ARCHIVE" \
  'vllm_recent_runs_20260407/vllm_external_8b_hb128_1812656/*' \
  -d "$VLLM_WORK/archive"

for rep in \
  "$VLLM_WORK"/archive/vllm_recent_runs_20260407/vllm_external_8b_hb128_1812656/nsys/*.nsys-rep
do
  name="$(basename "${rep%.nsys-rep}")"
  "$NSYS_BIN" export -f true -t sqlite \
    -o "$VLLM_WORK/sqlite/$name.sqlite" "$rep"
done
```

The local generator source was `spcl/atlahs` commit
`c7b8a4575822547bc266ae5030b823b1f7a24874` with the exact replacement
source stored at
`local_artifact/source_snapshots/atlahs_c7b8a457/inter_node_dependency.py`.
The replacement derives each rank's position from the actual per-channel
ring topology and fixes the final ring phase's step origin. Source/data
hashes:

```text
get_traced_events.py
  869cbc5169612655cd7b440a6107a47ec2b3808037ec84f4386e470852a53396
patched inter_node_dependency.py
  bcdbb3b7b509cf27c91009af0a84f139013dd79216a3a9f48d424f8ee2636b37
Clariden NPKit LL JSON
  770afcf0a72323f91404ce5859844b4f3032cf2d0054c87207d1813ebf4b7e23
Clariden NPKit Simple JSON
  f582139be3e100baaf19558d3d5b8269dc5bbbd23d5c35efbbadbf2374ff2b1c
```

Only the generator source change is needed for this result. As a
clean-control test,
`txt2bin` and LogGOPSim were rebuilt directly from unmodified ATLAHS
`c7b8a457`. Clean `txt2bin` produced a byte-identical BIN with SHA-256
`9cfa3b84b8a565189c5a7db25b7626bfdc6008b81405ccefc73c0e96f4b2c9ef`,
and clean LogGOPSim again returned exactly
`3,450,438,267 ns` at L=3.7 us. Unrelated local LogGOPSim diagnostic/jitter
changes are therefore not part of the vLLM provenance chain.

Install the pinned source snapshot and run:

```bash
git -C "$ATLAHS" checkout c7b8a4575822547bc266ae5030b823b1f7a24874
cp /path/to/SC_Tracing/local_artifact/source_snapshots/atlahs_c7b8a457/inter_node_dependency.py \
  "$ATLAHS/goal_gen/ai/nccl_goal_generator/generator_modules/data_dependency_modules/inter_node_dependency.py"
printf '%s  %s\n' \
  bcdbb3b7b509cf27c91009af0a84f139013dd79216a3a9f48d424f8ee2636b37 \
  "$ATLAHS/goal_gen/ai/nccl_goal_generator/generator_modules/data_dependency_modules/inter_node_dependency.py" \
  | sha256sum -c -

cd "$ATLAHS/goal_gen/ai/nccl_goal_generator"
python3 get_traced_events.py \
  --trace-dir "$VLLM_WORK/sqlite" \
  --output-dir "$VLLM_WORK/goal" \
  --npkit_file_Simple npkit_benchmark_results/clariden/npkit_data_summary_Simple.json \
  --npkit_file_LL npkit_benchmark_results/clariden/npkit_data_summary_LL.json \
  --merge-non-overlap \
  --unique-nic
```

Expected fresh GOAL:

```text
File:       InterNode_MicroEvents_Dependency.goal
Header:     num_ranks 2
Lines:      1,641,027
Bytes:      42,951,412
SHA-256:    740e3cef35e160ec47875924e199c615b1ab5e1dc3daf3d8ff4fe357cf2e50c4
GPU events: 193 events for each of GPUs 0 through 7
Max compute time reported by generator: 3,337,148,224 ns
```

The GOAL's two ranks represent the two nodes; its CPU lanes represent the
four GPUs on each node. Consequently LogGOPSim uses its default
`ranks-per-node=1` for this particular GOAL.

Convert and replay:

```bash
make -C "$ATLAHS/sim/LogGOPSim"
"$ATLAHS/sim/LogGOPSim/txt2bin" \
  -i "$VLLM_WORK/goal/InterNode_MicroEvents_Dependency.goal" \
  -o "$VLLM_WORK/goal/simulation.bin"

"$ATLAHS/sim/LogGOPSim/LogGOPSim" \
  -f "$VLLM_WORK/goal/simulation.bin" \
  --LogGOPS_L 3700 \
  --LogGOPS_o 200 \
  --LogGOPS_g 5 \
  --LogGOPS_G 0.04 \
  --LogGOPS_S 0 \
  -b
```

Expected BIN and replay:

```text
BIN bytes:       30,207,946
BIN SHA-256:     9cfa3b84b8a565189c5a7db25b7626bfdc6008b81405ccefc73c0e96f4b2c9ef
LGS events:      709,740
Average FCT:     20,946.695758
Fresh Host 0:    3,450,438,267 ns
Archived Host 0: 3,450,438,267 ns
Archived Host 1: 3,450,416,692 ns
```

The exact Host-0 integer match is the strongest raw-provenance check in this
handoff.

### Sampled sensitivity sweep and unresolved paper curve

`local_artifact/scripts/run_vllm_full_goal_lgs_sweeps.py` runs:

- latency at L = 0, 5, 10, 25, 50, 100, 250, 500, 750, and 1000 us,
  with `G=0.04 ns/byte`;
- bandwidth at `G=0.00 ... 0.16 ns/byte` in 0.01 steps, with `L=4000 ns`;
- `o=200 ns`, `g=5 ns`, and `S=0`.

Example:

```bash
python3 local_artifact/scripts/run_vllm_full_goal_lgs_sweeps.py \
  --bin "$VLLM_WORK/goal/simulation.bin" \
  --simulator "$ATLAHS/sim/LogGOPSim/LogGOPSim" \
  --out "$VLLM_WORK/lgs"
```

This full raw-trace curve is 13.827944% away from the paper latency CSV at
the sampled points and 20.315004% away from the paper bandwidth CSV. It is
slower than the paper curve even though it exactly reproduces the archived
job's runtime.

The likely missing stage is visible in the binary sizes:

```text
fresh full job-1812656 BIN        30,207,946 bytes
preserved vllm_8b_128tok/lgs.bin   8,491,894 bytes
preserved vllm_8b_32tok/lgs.bin    2,122,870 bytes
preserved vllm_8b_512tok/lgs.bin  33,967,990 bytes
```

The preserved 32/128/512-token BIN sizes scale essentially 1:4:16. This
strongly suggests a paper-specific crop, token-window extraction, or
synthetic repetition step. No script/configuration creating the 8.5 MB BIN
was found in the accessible commits, worktrees, shell evidence, or archive.
The 8.5 MB BIN and paper CSVs are derived/cache evidence; they are not
acceptable replacements for the two exact NSYS reports in a clean AE run.

## Verification

Verify all small committed evidence:

```bash
python3 local_artifact/verify_manifests.py
```

If the large local vLLM archive is available, also stream and hash its exact
members without extracting:

```bash
python3 local_artifact/verify_manifests.py \
  --vllm-archive /path/to/vllm_recent_runs_20260407.zip
```

The latter reads roughly 1.1 GB to verify the container hash, then streams
only the exact job-1812656 members. It does not modify or extract the
archive.

Use Python 3.9 or newer for the artifact pipelines. The branch uses
`argparse.BooleanOptionalAction`, which is unavailable in Python 3.8. On the
local WSL host, the handoff verifier passed all 71 archive/file checks and
the existing repository suite produced 12 passes plus one quick-check
failure because that test launched the system Python 3.8. The exact failing
pipeline's `--help` command succeeds under the installed Python 3.11. The
clean artifact environment documented by the base branch uses Python 3.12.

## Remaining AD/AE work

1. Copy the exact vLLM archive or only the two exact NSYS reports plus the
   three small provenance logs to a clearly named directory under remote
   `/mnt/scratch/`, using a resumable checksummed transfer. Do not put them
   in the remote home directory or Git. Verify the hashes from
   `vllm_figure6_files.csv`.
2. Reconcile the ATLAHS ring-position source change into the artifact
   generator or pin the external ATLAHS commit plus the exact committed
   source snapshot in the AD.
3. Recover or reconstruct the paper-specific vLLM 30.2 MB to 8.5 MB
   crop/window/repetition step. Until then, report both truths: exact raw job
   replay succeeds, but the paper sensitivity CSV is not reproduced.
4. For Figure 6 Llama, either:
   - keep the scientifically accurate metadata-to-plot claim; or
   - download the 32 public N32/GPU128 reports to scratch, hash them,
     regenerate the metadata, and upgrade the claim to raw-to-plot.
5. Correct or annotate the model labels:
   - Figure 5 observed input: Llama 7B/6.74B N4/GPU16/DP16.
   - Figure 6 Llama observed input: Llama 7B N32/GPU128/DP128.
   - Figure 6 vLLM exact input: Llama-3.1-8B-Instruct N2/GPU8/TP8,
     128 tokens.
6. Preserve the Figure 4 distinction: the older campaign generates the
   paper curve but has 0.5–256 MiB messages; corrected job 1791883 matches
   the prose but not the plotted curve.
7. Repeat final commands on the eventual `final_AE` commit and record its
   exact hash, tool versions, wall time, peak RSS, output hashes, and
   comparison metrics.

## Eligible clean-rerun inputs

Eligible original/static inputs:

- original `.nsys-rep` reports listed in the manifests;
- public/static `.goal` and `.bin` files when their identity matches the
  target configuration;
- NCCL logs, run manifests, and generator configuration files used to
  establish identity.

Not eligible as substitutes:

- SQLite exports;
- `collective_instances.csv`, `comm_ring_info.csv`, or other generated
  metadata;
- solver cache JSON;
- sensitivity/runtime CSVs;
- plots;
- the unexplained 8.5 MB vLLM `lgs.bin`.

Those derived files remain useful for regression comparisons and provenance,
but a clean AE claim must state explicitly when it begins from them.
