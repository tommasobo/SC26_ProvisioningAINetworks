# Provisioning Networks for AI Supercomputers

This repository contains the artifact for reproducing the computational
figures in the paper. Execution traces are treated as inputs: small trace
sets may be kept with the artifact, while larger trace sets should be
downloaded from the public repository to a scratch filesystem.

Repository: <https://github.com/tommasobo/SC26_ProvisioningAINetworks>

Public traces: <http://storage2.spcl.ethz.ch/traces/ai/>

Two workflows are provided:

- `reproduce_quick.sh` generates Figures 1 and 3 to 10 from the supplied
  inputs. Figure 2 is a method diagram.
- `reproduce_full.sh` runs the numerical analysis for Figures 3 to 6 and
  passes the generated CSV files to the paper-style plotters. When raw NSYS
  reports are supplied, it first performs trace export and input generation.

Large intermediate files should be stored on a scratch filesystem.

## Installation

Python 3.10 or newer is required:

```bash
git clone https://github.com/tommasobo/SC26_ProvisioningAINetworks.git
cd SC26_ProvisioningAINetworks
git checkout main
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

For the full workflow, also install `requirements-dev.txt` and
`requirements-tierc.txt`. The raw-trace path requires the `nsys` command
from NVIDIA Nsight Systems. The analysis stages require a working Gurobi
installation and license. Academics can
obtain a free Gurobi license from
<https://www.gurobi.com/academia/academic-program-and-licenses/>.
The LogGOPSim example additionally requires `g++`, `gengetopt`, and `re2c`.

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
| 8 | `scripts/fig08_09_cluster_params_cost.py` | `fig8_network_parameters.pdf` |
| 9 | `scripts/fig08_09_cluster_params_cost.py` | `fig9_network_cost.pdf` |
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
task summaries, and the final paper-style plots below the selected scratch
directory. The final PDFs are written to `<scratch>/figures/`. Plan for at
least 4 CPU cores and 128 GB of RAM.

For a trace-to-plot run, prepare the required NSYS reports and add a trace
root:

```bash
./reproduce_full.sh \
  --scratch /path/to/scratch/provisioning_artifact \
  --trace-root /path/to/scratch/raw_traces \
  --workers 4
```

The trace root contains `fig3/ch1`, `fig3/auto`, `fig4`, `fig5`, and
`fig6/llama`, with the corresponding `.nsys-rep` files in each directory.
Small trace sets can be copied from the artifact when provided. Larger trace
sets should be downloaded from the public trace repository into scratch.
Supplying `--trace-root` enables NSYS export, SQLite conversion,
communication-schedule generation, numerical analysis, and plotting through
the same entry point.

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

The Grok 4k analysis covers the 4,096-GPU workload and is not part of the
default workflow. Enable it only when enough memory, compute time, and scratch
space are available:

```bash
./reproduce_full.sh --slurm --expensive_run \
  --partition <large-memory-partition> \
  --grok-analysis-dir /scratch/path/to/grok/N1024/analysis \
  --scratch /scratch/path/to/output
```

Plan for at least 1 TB of RAM and allow approximately 3 to 5 days for the
complete latency and bandwidth analysis. Actual requirements depend on the
solver configuration and available parallelism. Check the selected
partition's memory and wall-time limits before submission.

## Repository contents

- `data/` contains the supplied inputs used by the plotting workflows.
- `results/reproduced/` and `local_artifact/results/` contain the selected
  numerical results.
- `local_artifact/manifests/` records input and output identities.
- `docs/ad/` contains the combined AD/AE source and PDF.
