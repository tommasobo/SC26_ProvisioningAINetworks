#!/usr/bin/env python3
"""
Master entry point for the SC26 artifact.

Regenerates every figure reported in the paper
"Provisioning Networks for AI Supercomputers: A Trace-Driven Study of
Performance Sensitivity at Unprecedented Scale" from the packaged data
under ``data/``. Outputs are written to ``figures/``.

Usage:
    python3 reproduce_all.py              # run every figure
    python3 reproduce_all.py --only 3 4   # run only paper figures 3 and 4
    python3 reproduce_all.py --list       # show the mapping

Each entry below is a (paper_figure_number, script_name, output_files).
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"
FIGURES = HERE / "figures"

FIGURE_MAP = [
    (1,  "fig01_sensitivity_maps.py",
        ["fig_2d_sensitivity_workloads.pdf"]),
    (3,  "fig03_allreduce_1x4.py",
        ["fig3_sensitivity_1x4.pdf"]),
    (4,  "fig04_mixed_collectives.py",
        ["fig_mixed_16n_ch1.pdf"]),
    (5,  "fig05_llama_iteration.py",
        ["fig5_llama7b.pdf"]),
    (6,  "fig06_sensitivity_grid.py",
        ["fig_3x3_sensitivity.pdf"]),
    (7,  "fig07_memory_scaling.py",
        ["fig6_grok_memory.pdf"]),
    (8,  "fig08_09_cluster_params_cost.py",
        ["fig8_network_parameters.pdf"]),
    (9,  "fig08_09_cluster_params_cost.py",
        ["fig9_network_cost.pdf"]),
    (10, "fig10_jitter.py",
        ["fig_jitter_3panel.pdf"]),
]


def run_script(name: str) -> float:
    script = SCRIPTS / name
    if not script.exists():
        raise FileNotFoundError(script)
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, str(script)],
                       capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        print(f"\n[FAIL] {name} (exit {r.returncode})")
        print(r.stdout)
        print(r.stderr)
        raise SystemExit(r.returncode)
    return dt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", type=int, default=None,
                    help="paper figure numbers to regenerate")
    ap.add_argument("--list", action="store_true",
                    help="print the figure mapping and exit")
    ap.add_argument("--pipeline", action="store_true",
                    help="also run the upstream LogGOPSim pipeline demo on "
                         "the shipped demo GOAL trace (builds LogGOPSim from "
                         "source if not already built)")
    args = ap.parse_args()

    if args.list:
        print(f"{'Paper Fig':<10} {'Script':<40} {'Output(s)'}")
        print("-" * 90)
        for num, script, outs in FIGURE_MAP:
            print(f"{num:<10} {script:<40} {', '.join(outs)}")
        return 0

    if args.pipeline:
        print("=== Pipeline demo (LogGOPSim on shipped demo GOAL) ===")
        pipe = HERE / "pipeline" / "demo.py"
        r = subprocess.run([sys.executable, str(pipe)])
        if r.returncode != 0:
            return r.returncode
        print()

    selected = set(args.only) if args.only else None
    selected_rows = [
        row for row in FIGURE_MAP
        if selected is None or row[0] in selected
    ]
    grouped: dict[str, tuple[list[int], list[str]]] = {}
    for num, script, outs in selected_rows:
        if script not in grouped:
            grouped[script] = ([], [])
        numbers, outputs = grouped[script]
        numbers.append(num)
        outputs.extend(out for out in outs if out not in outputs)

    missing_outputs: list[Path] = []
    total_t = 0.0
    for script, (numbers, outs) in grouped.items():
        figure_label = ", ".join(str(number) for number in numbers)
        print(f"[Fig {figure_label}] {script}")
        dt = run_script(script)
        total_t += dt
        for out in outs:
            p = FIGURES / out
            status = "OK" if p.exists() else "MISSING"
            if not p.exists():
                missing_outputs.append(p)
            print(f"   -> {p.relative_to(HERE)}  [{status}]")
        print(f"   ({dt:.1f}s)")

    print(f"\nDone. Total: {total_t:.1f}s. Outputs in {FIGURES.relative_to(HERE)}/")
    if missing_outputs:
        print(
            "Missing expected outputs: "
            + ", ".join(str(path.relative_to(HERE)) for path in missing_outputs),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
