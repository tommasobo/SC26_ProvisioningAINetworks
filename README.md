# Provisioning Networks for AI Supercomputers

This branch is the SC26 artifact freeze for the paper. The default workflow is
a local redraw of Figures 1 and 3 to 10 from compact data. Figure 2 is a method
diagram and has no computational output. The full workflow reruns the bounded
solver checks for Figures 3, 4, and 6 and verifies the best recovered Figure 5
result. Large traces, solver caches, and temporary files stay outside the
repository.

The quick workflow takes about 15 seconds on Alps. It does not download traces,
run Gurobi, or rerun Grok at 4,096 GPUs.

## Setup

Python 3.10 or newer is required:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`uv venv --python 3.11 .venv` and `uv pip install --python
.venv/bin/python -r requirements.txt` are equivalent when `uv` is available.

For the full workflow, also install `requirements-dev.txt`. It needs a working
Gurobi license; the small LogGOPSim demo needs `g++`, `gengetopt`, and `re2c`.

## Quick local reproduction

```bash
./reproduce_quick.sh
```

The command redraws these files under `figures/`:

| Paper figure | Plot script | Output |
| --- | --- | --- |
| 1 | `scripts/fig01_sensitivity_maps.py` | `fig_2d_sensitivity_workloads.pdf` |
| 3 | `scripts/fig03_allreduce_1x4.py` | `fig3_sensitivity_1x4.pdf` |
| 4 | `scripts/fig04_mixed_collectives.py` | `fig_mixed_16n_ch1.pdf` |
| 5 | `scripts/fig05_llama_iteration.py` | `fig5_llama7b.pdf` |
| 6 | `scripts/fig06_sensitivity_grid.py` | `fig_3x3_sensitivity.pdf` |
| 7 | `scripts/fig07_memory_scaling.py` | `fig6_grok_memory.pdf` |
| 8 and 9 | `scripts/fig08_09_cluster_params_cost.py` | `fig_network_perf_combined.pdf` |
| 10 | `scripts/fig10_jitter.py` | `fig_jitter_3panel.pdf` |

Figure 5 uses the closest recovered raw-derived Composite curve, which differs
from the paper CSV by at most 0.014853%. Grok 4k panels, the Figure 5
Monolithic curve, and Figures 1 and 7 to 10 use the existing compact data.

## Full local reproduction

Use a scratch directory with enough free space:

```bash
./reproduce_full.sh \
  --scratch /path/to/scratch/provisioning_artifact \
  --workers 4
```

The full script performs the quick redraw, manifest and test checks, the small
LogGOPSim demo, fresh-cache metadata Composite checks for Figures 3 and 4, a
comparison of the recovered Figure 5 curve, and fresh-cache Figure 6 Llama
latency and bandwidth checks. Each default experiment is bounded to about
45 minutes. The Figure 6 checks are the longest and previously took about 19
and 31 minutes. Both Figure 6 tasks use the four physical NIC queues. July
one-queue results and a final repeated one-queue result are retained under
`results/reproduced/fig6/` to document the investigated alternative.

Large raw NSYS and GOAL files are not committed. Their exact hashes and
provenance are under `local_artifact/manifests/`. The full script starts from
the compact metadata that is present in the repository.

## Alps and Slurm

Do not run the full workflow on a login node. Submit the work as separate
batch jobs:

```bash
./reproduce_full.sh --slurm \
  --account a-g200 \
  --partition normal \
  --scratch /iopsstor/scratch/cscs/$USER/provisioning_artifact \
  --workers 4
```

The launcher runs independent jobs concurrently and serializes the two Figure
6 sweeps to respect Gurobi license limits. Job IDs are written to
`submitted_jobs.txt` below the selected scratch directory.

## Expensive Grok 4k option

Grok at 4,096 GPUs is disabled by default. Its paper CSVs are used for plots.
The full launcher exposes the cold Composite latency and bandwidth workflows
only when both the explicit gate and N1024 metadata are supplied:

```bash
./reproduce_full.sh --slurm --expensive_run \
  --grok-analysis-dir /scratch/path/to/grok/N1024/analysis \
  --scratch /scratch/path/to/output
```

Do not enable this option without confirming the input, RAM, allocation, and
time. The Grok solver jobs run after the Figure 6 jobs and are serialized with
each other. The historical cold latency solve took about 4.4 hours. No Grok
4k experiment was run while preparing this branch.

## Data and interpretation

- `data/output/` contains the compact paper plotting inputs.
- `data/workspaces/llama7b_n32_spcl_20260407/` contains the Figure 6 Llama
  metadata used by the bounded full rerun.
- `local_artifact/results/` contains the strongest compact raw-derived results
  for Figures 3 to 6.
- `local_artifact/figures/SC26_paper_vs_reproduced_figures_3_to_6.pdf` is the
  retained paper-versus-result comparison bundle from the local handoff.
- `results/reproduced/` contains selected Alps results that improved on the
  local handoff, including the historical four-NIC Figure 3 auto-channel run.
- `local_artifact/manifests/` records hashes and raw-input identities.
- `docs/REPRODUCTION_REPORT.md` gives the match status and remaining gaps.
- `docs/comparison/SC26_paper_vs_artifact.pdf` places each paper plot above
  its reproduced or compact-data result.
- `docs/provenance/` retains the detailed Alps and local handoff notes.
- `docs/ad/` contains the final combined AD/AE in LaTeX and PDF form.

The Figure 1 phase map combines one-dimensional latency and bandwidth sweeps;
it is not a joint two-dimensional simulation. The Figure 6 Llama metadata
identify Llama 7B at N32/GPU128 even though the paper label says 70B. Figures
8 and 9 are plot-only because their published latency, bandwidth, and cost
data are embedded in the plotting script.

For exact commands, discrepancies, and provenance, read
`docs/REPRODUCTION_REPORT.md`.
