# SC26 Artifact — Provisioning Networks for AI Supercomputers

This artifact reproduces the figures of the paper
*"Provisioning Networks for AI Supercomputers: A Trace-Driven Study of
Performance Sensitivity at Unprecedented Scale"* and provides the full
pipeline used to derive them from raw execution traces.

## End-to-end reproduction (figures only, ~1 minute)

Four commands, no GPU, no special hardware:

```bash
git clone -b main https://github.com/tommasobo/SC_Tracing.git
cd SC_Tracing
pip install -r requirements.txt
python3 reproduce_all.py
```

Generated PDFs and PNGs appear under `figures/`.

## End-to-end reproduction (figures + pipeline demo, ~2 minutes)

Same three commands plus `--pipeline`, which builds LogGOPSim from
source and replays a small demo GOAL trace through the LGS stage
before running the figure scripts:

```bash
apt-get install g++ gengetopt re2c          # build deps for LogGOPSim
python3 reproduce_all.py --pipeline
```

## Pipeline stages

The paper's pipeline has four stages. The artifact supplies the code
for all of them and the packaged outputs that let reviewers bypass
the expensive ones:

```
┌────────────┐    ┌──────────┐    ┌──────────────────┐    ┌─────────┐
│ Raw traces │───▶│   GOAL   │───▶│ Composite-LP     │───▶│ Figure  │
│  (nsys)    │    │ (A2)     │    │  or LogGOPSim    │    │ scripts │
└────────────┘    └──────────┘    │  or Monolithic-LP│    └─────────┘
   Stage 1          Stage 2       └──────────────────┘       Stage 4
                                           Stage 3
```

| Stage | What it does | Code in artifact | Runs on reviewer machine? |
|-------|--------------|------------------|---------------------------|
| 1. Raw → GOAL | NVIDIA Nsight trace + nccl_generator emits GOAL schedules | documented only | No (needs a GPU cluster + NCCL; we ship the GOAL outputs as artifact $A_2$) |
| 2. GOAL download | Fetch GOAL traces from $A_2$ | `wget` example | Yes |
| 3a. Composite-LP sweep | Per-signature parametric LP + program-level composition | `solver/`, `pipeline/run_composite_lp.py` | Yes (needs Gurobi and a proper NCCL GOAL) |
| 3b. LogGOPSim replay | Validation runtime | `tools/LogGOPSim/`, `pipeline/run_lgs.py` | Yes |
| 3c. Monolithic LP | Single full-trace LP (paper baseline for Figs 5, 7) | `solver/` (`main.py -a sensitivity --skip-composition`) | Only at small scales — at 4,096 GPUs it requires tens of TB of RAM and we ship the results |
| 4. Plotting | Figure generation from the sensitivity CSVs | `scripts/fig*.py`, `reproduce_all.py` | Yes (default path, ~1 min) |

## Layout

```
.
├── README.md
├── requirements.txt          # matplotlib, numpy, pandas
├── reproduce_all.py          # master entry: figures (default) + --pipeline
├── scripts/                  # figure generators (one per paper figure)
├── solver/                   # Composite-LP and Monolithic-LP solver (Python)
├── tools/LogGOPSim/          # LogGOPSim source + Makefile (build with pipeline/build_tools.sh)
├── pipeline/                 # thin drivers over solver/ and tools/LogGOPSim/
│   ├── build_tools.sh
│   ├── demo.py
│   ├── run_composite_lp.py
│   └── run_lgs.py
├── data/
│   ├── traces/demo_allreduce_16r_1MiB.goal  # tiny GOAL for the pipeline demo
│   ├── output/...                            # precomputed sensitivity CSVs
│   └── workspaces/...                        # precomputed per-workload CSVs
├── figures/                  # generated figures (created on run)
└── latex/                    # AD LaTeX source
```

## Paper figure mapping

| Paper Fig | Script                               | Output                              |
| --------- | ------------------------------------ | ----------------------------------- |
| 1         | `fig01_sensitivity_maps.py`          | `fig_2d_sensitivity_workloads.pdf`  |
| 2         | *(diagram, no script)*               | —                                   |
| 3         | `fig03_allreduce_1x4.py`             | `fig3_sensitivity_1x4.pdf`          |
| 4         | `fig04_mixed_collectives.py`         | `fig_mixed_16n_ch1.pdf`             |
| 5         | `fig05_llama_iteration.py`           | `fig5_llama7b.pdf`                  |
| 6         | `fig06_sensitivity_grid.py`          | `fig_3x3_sensitivity.pdf`           |
| 7         | `fig07_memory_scaling.py`            | `fig6_grok_memory.pdf`              |
| 8         | `fig08_09_cluster_params_cost.py`    | `fig_network_perf_combined.pdf`     |
| 9         | `fig08_09_cluster_params_cost.py`    | `fig_network_perf_combined.pdf`     |
| 10        | `fig10_jitter.py`                    | `fig_jitter_3panel.pdf`             |

Figures 8 and 9 are the two panels of a single combined plot.

## Precomputed outputs for expensive pipeline stages

Several upstream stages are too resource-intensive to run on a
typical reviewer machine. We ship their **outputs** as CSV so
figure reproduction is fully decoupled from the original hardware:

- **Monolithic LP at scale.** The full-trace LP baseline used in
  Figures 5 and 7 requires ~14 GiB at Llama 8B / 16 GPUs (83 min)
  and would require tens of TiB at 4,096 GPUs. We ship the
  small-scale `full_runtime.csv` directly.
- **LogGOPSim replay of Grok 314B on 4,096 GPUs.** The replay emits
  a ~1.3 TiB GOAL schedule and takes hours; we ship the
  `lgs_points.csv` result.
- **Composite-LP sweeps at full scale.** Llama 70B on 128 GPUs and
  Grok 314B on 4,096 GPUs each take 1–10 min *and* require a Gurobi
  license. We ship the sensitivity CSVs so figures are always
  reproducible, and expose `pipeline/run_composite_lp.py` for
  reviewers who want to regenerate them.
- **Hardware reference measurements.** Collected on the Alps
  supercomputer (NVIDIA GH200, Slingshot-11) and the Azure ND
  GB200 v6 cluster; both shipped as static CSV.

The packaged CSVs live under `data/output/` and `data/workspaces/`.

## Running the pipeline on real workloads

To drive the pipeline on one of the released traces from $A_2$
(`http://storage2.spcl.ethz.ch/traces/ai/`), download a per-workload
sub-tree (each includes the GOAL file and a `comm_dep.csv` that
disambiguates sends/recvs), then invoke the pipeline drivers:

```bash
# Download one workload
wget -r -np -nH --cut-dirs=2 \
    http://storage2.spcl.ethz.ch/traces/ai/llama3_3_n32/

# Composite-LP sweep over latency
python3 pipeline/run_composite_lp.py \
    --goal   llama3_3_n32/output.goal \
    --comm-dep llama3_3_n32/InterNode_MicroEvents_Dependency.exact.comm_dep.csv \
    --out    out/llama_n32_composed.csv \
    --l-min 0 --l-max 1000000 --step 50000

# LogGOPSim replay for a latency point
python3 pipeline/run_lgs.py \
    --goal llama3_3_n32/output.goal --L 1000
```

## System requirements

- Python 3.8+
- ~200 MiB of free disk
- No GPU; no special hardware
- For the `--pipeline` path: `g++`, `gengetopt`, `re2c`
- For Composite-LP / Monolithic-LP runs: Gurobi 10.0+
  (free academic license at `gurobi.com/academia`)

Tested on Ubuntu 22.04 (WSL2) with Python 3.8.10, Matplotlib 3.7,
g++ 9.4, LogGOPSim 1.x (shipped source).
