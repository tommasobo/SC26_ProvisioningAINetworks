# Selected reproduction results

This directory contains the compact results selected after comparing the June
scratch rerun, the July Alps rerun, and the local artifact handoff.

- `fig3/` contains the closest recovered raw-trace Monolithic-LP curves.
- `fig6/` contains July one-NIC and final one-NIC/four-NIC cold metadata
  checks.
- `summary.json` records point counts and relative differences for Figures 3
  to 6.
- The Figure 4 and Figure 5 selected CSVs remain under
  `local_artifact/results/` because they are covered by that handoff's SHA-256
  manifest.
- The two archived Figure 6 Llama comparison tables remain under
  `results/revalidation/figures_end_to_end/` because their paths and hashes
  are recorded by `local_artifact/manifests/llama_figure6_local_metadata.csv`.

All comparison percentages use the compact CSV consumed by the paper plotting
script as the reference. See `docs/REPRODUCTION_REPORT.md` for configuration
details and unresolved provenance differences.
