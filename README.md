# Provisioning Networks for AI Supercomputers

This repository contains the artifact for reproducing the computational
figures in the paper. It assumes that execution traces have already been
collected. Public traces are available from the
[SPCL trace repository](http://storage2.spcl.ethz.ch/traces/ai/).

Two workflows are provided:

- `reproduce_quick.sh` generates Figures 1 and 3 to 10 from the supplied
  inputs. Figure 2 is a method diagram.
- `reproduce_full.sh` additionally runs the analysis and validation stages
  for Figures 3 to 6.

Large intermediate files should be stored on a scratch filesystem.

## Installation

Python 3.10 or newer is required:

```bash
git clone https://github.com/tommasobo/SC26_ProvisioningAINetworks.git
cd SC26_ProvisioningAINetworks
git checkout artifact_freeze
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For the full workflow, also install `requirements-dev.txt`. The analysis
stages require a working Gurobi installation and license. The LogGOPSim
example additionally requires `g++`, `gengetopt`, and `re2c`.

## Quick reproduction

```bash
./reproduce_quick.sh
```

Allow about one minute. The output files are:

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

## Full local reproduction

Use a scratch directory with sufficient free space:

```bash
./reproduce_full.sh \
  --scratch /path/to/scratch/provisioning_artifact \
  --workers 4
```

Allow up to eight hours, depending on the machine, solver license
availability, and selected worker count. Most individual analysis tasks
should be allowed up to one hour. The script writes result CSV files, logs,
and task summaries below the selected scratch directory.

## Alps and Slurm

Submit longer work from a compute allocation:

```bash
./reproduce_full.sh --slurm \
  --account <account> \
  --partition normal \
  --scratch /iopsstor/scratch/cscs/$USER/provisioning_artifact \
  --workers 4
```

Independent tasks are submitted separately. Submitted job IDs are written to
`submitted_jobs.txt` below the selected scratch directory.

## Optional large run

The Grok 4k analysis is not part of the default workflow. Enable it only when
enough memory, compute time, and scratch space are available:

```bash
./reproduce_full.sh --slurm --expensive_run \
  --partition <large-memory-partition> \
  --grok-analysis-dir /scratch/path/to/grok/N1024/analysis \
  --scratch /scratch/path/to/output
```

Plan for at least 512 GB of RAM and allow approximately 3 to 5 days for the
complete latency and bandwidth analysis. Actual requirements depend on the
solver configuration and available parallelism. Check the selected
partition's memory and wall-time limits before submission.

## Repository contents

- `data/` contains the supplied inputs used by the plotting workflows.
- `results/reproduced/` and `local_artifact/results/` contain the selected
  numerical results.
- `local_artifact/manifests/` records input and output identities.
- `docs/REPRODUCTION_REPORT.md` contains the detailed numerical comparison.
- `docs/comparison/SC26_paper_vs_artifact.pdf` places each paper plot above
  the corresponding artifact result.
- `docs/ad/` contains the combined AD/AE source and PDF.

The full numerical results, provenance, and known limitations are recorded in
`docs/REPRODUCTION_REPORT.md`.
