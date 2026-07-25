#!/usr/bin/env bash
# Run bounded upstream checks locally or as separate Slurm jobs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE=local
EXPENSIVE=0
DRY_RUN=0
WORKERS=4
ACCOUNT="${SLURM_ACCOUNT:-a-g200}"
PARTITION="${SLURM_PARTITION:-normal}"
SCRATCH_DIR="${ARTIFACT_SCRATCH:-${SCRATCH:-/tmp}/sc26_provisioning_artifact_${USER:-user}}"
GROK_ANALYSIS_DIR=""

usage() {
    cat <<'EOF'
Usage: ./reproduce_full.sh [options]

Options:
  --local                  Run tasks sequentially on the current machine (default).
  --slurm                  Submit tasks as separate Slurm jobs.
  --scratch DIR            Working directory for large outputs.
  --workers N              Solver workers per task (default: 4).
  --account NAME           Slurm account (default: $SLURM_ACCOUNT or a-g200).
  --partition NAME         Slurm partition (default: $SLURM_PARTITION or normal).
  --expensive_run          Enable the gated Grok 4096-GPU tasks.
  --grok-analysis-dir DIR  N1024 metadata input for --expensive_run.
  --dry-run                Print commands or Slurm submissions without running them.
  -h, --help               Show this help.

The default run never executes Grok 4096-GPU experiments. Those tasks require
both --expensive_run and an explicit --grok-analysis-dir. The complete Grok
latency and bandwidth analysis should be run on a large-memory node with at
least 1 TB of RAM and may require approximately 3 to 5 days.
EOF
}

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --local) MODE=local ;;
        --slurm) MODE=slurm ;;
        --scratch)
            shift
            [[ "$#" -gt 0 ]] || { echo "error: --scratch needs a path" >&2; exit 2; }
            SCRATCH_DIR="$1"
            ;;
        --workers)
            shift
            [[ "$#" -gt 0 ]] || { echo "error: --workers needs a number" >&2; exit 2; }
            WORKERS="$1"
            ;;
        --account)
            shift
            [[ "$#" -gt 0 ]] || { echo "error: --account needs a name" >&2; exit 2; }
            ACCOUNT="$1"
            ;;
        --partition)
            shift
            [[ "$#" -gt 0 ]] || { echo "error: --partition needs a name" >&2; exit 2; }
            PARTITION="$1"
            ;;
        --expensive_run) EXPENSIVE=1 ;;
        --grok-analysis-dir)
            shift
            [[ "$#" -gt 0 ]] || {
                echo "error: --grok-analysis-dir needs a path" >&2
                exit 2
            }
            GROK_ANALYSIS_DIR="$1"
            ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

[[ "$WORKERS" =~ ^[1-9][0-9]*$ ]] || {
    echo "error: --workers must be a positive integer" >&2
    exit 2
}

if [[ "$EXPENSIVE" -eq 1 && -z "$GROK_ANALYSIS_DIR" ]]; then
    echo "error: --expensive_run requires --grok-analysis-dir DIR" >&2
    exit 2
fi
if [[ "$EXPENSIVE" -eq 0 && -n "$GROK_ANALYSIS_DIR" ]]; then
    echo "error: --grok-analysis-dir is accepted only with --expensive_run" >&2
    exit 2
fi
if [[ "$EXPENSIVE" -eq 1 ]]; then
    cat >&2 <<'EOF'
warning: Grok 4096-GPU analysis is a multi-day workload.
         Allocate at least 1 TB RAM and approximately 3 to 5 days.
EOF
fi

if [[ -n "${ARTIFACT_PYTHON:-}" ]]; then
    PYTHON_BIN="$ARTIFACT_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
else
    PYTHON_BIN="$(command -v python3)"
fi

tasks=(core demo fig3 fig4 fig5 fig6-latency fig6-bandwidth)
if [[ "$EXPENSIVE" -eq 1 ]]; then
    tasks+=(grok4096-latency grok4096-bandwidth)
fi

mkdir -p "$SCRATCH_DIR/logs"

if [[ "$MODE" == local ]]; then
    for task in "${tasks[@]}"; do
        cmd=(
            "$PYTHON_BIN" "$ROOT/scripts/reproduce_full_task.py"
            --task "$task"
            --scratch "$SCRATCH_DIR"
            --workers "$WORKERS"
        )
        if [[ "$EXPENSIVE" -eq 1 ]]; then
            cmd+=(--grok-analysis-dir "$GROK_ANALYSIS_DIR")
        fi
        printf '>>>'
        printf ' %q' "${cmd[@]}"
        printf '\n'
        if [[ "$DRY_RUN" -eq 0 ]]; then
            "${cmd[@]}"
        fi
    done
else
    command -v sbatch >/dev/null 2>&1 || {
        echo "error: sbatch was not found" >&2
        exit 3
    }
    submitted=()
    fig6_latency_job=""
    fig6_bandwidth_job=""
    grok_latency_job=""
    for task in "${tasks[@]}"; do
        time_limit="01:00:00"
        memory="128G"
        if [[ "$task" == grok4096-latency ]]; then
            time_limit="1-00:00:00"
            memory="1024G"
        elif [[ "$task" == grok4096-bandwidth ]]; then
            time_limit="4-00:00:00"
            memory="1024G"
        fi
        export_spec="ALL,ARTIFACT_ROOT=$ROOT,ARTIFACT_TASK=$task"
        export_spec+=",ARTIFACT_SCRATCH=$SCRATCH_DIR,ARTIFACT_WORKERS=$WORKERS"
        if [[ -n "$GROK_ANALYSIS_DIR" ]]; then
            export_spec+=",ARTIFACT_GROK_ANALYSIS_DIR=$GROK_ANALYSIS_DIR"
        fi
        dependency_args=()
        if [[ "$task" == fig6-bandwidth && -n "$fig6_latency_job" ]]; then
            dependency_args=(--dependency "afterany:$fig6_latency_job")
        elif [[ "$task" == grok4096-latency && -n "$fig6_bandwidth_job" ]]; then
            dependency_args=(--dependency "afterany:$fig6_bandwidth_job")
        elif [[ "$task" == grok4096-bandwidth && -n "$grok_latency_job" ]]; then
            dependency_args=(--dependency "afterany:$grok_latency_job")
        fi
        cmd=(
            sbatch --parsable
            --account "$ACCOUNT"
            --partition "$PARTITION"
            --time "$time_limit"
            --mem "$memory"
            --job-name "sc26-${task}"
            --output "$SCRATCH_DIR/logs/${task}_%j.out"
            --error "$SCRATCH_DIR/logs/${task}_%j.err"
            --export "$export_spec"
            "${dependency_args[@]}"
            "$ROOT/slurm/reproduce_task.sbatch"
        )
        printf '>>>'
        printf ' %q' "${cmd[@]}"
        printf '\n'
        if [[ "$DRY_RUN" -eq 0 ]]; then
            job_id="$("${cmd[@]}")"
            submitted+=("$task:$job_id")
            if [[ "$task" == fig6-latency ]]; then
                fig6_latency_job="$job_id"
            elif [[ "$task" == fig6-bandwidth ]]; then
                fig6_bandwidth_job="$job_id"
            elif [[ "$task" == grok4096-latency ]]; then
                grok_latency_job="$job_id"
            fi
        fi
    done
    if [[ "${#submitted[@]}" -gt 0 ]]; then
        printf '%s\n' "${submitted[@]}" | tee "$SCRATCH_DIR/submitted_jobs.txt"
        echo "Monitor with: squeue -j $(printf '%s,' "${submitted[@]#*:}" | sed 's/,$//')"
    fi
fi
