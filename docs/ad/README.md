# SC26 AD/AE appendix

This directory contains the final combined Artifact Description and Artifact
Evaluation appendix:

- `ad_ae_appendix.tex`: submission source
- `ad_ae_appendix.pdf`: compiled submission PDF
- `IEEEtran.cls` and `sc26repro.sty`: unchanged files from the official SC26
  template

The explanation and example tags in the source are commented out. A normal
TeX Live installation can build the PDF with:

```bash
make
```

The Makefile runs `pdflatex` three times, as in the official template.

The appendix documents `./reproduce_quick.sh` and `./reproduce_full.sh`.
The full script runs locally by default and supports Slurm. Grok 4k and the
other high-cost stages remain disabled unless `--expensive_run` is supplied.
The full 4,096-GPU Grok 4k analysis should be allocated at least 1 TB of RAM and
approximately 3 to 5 days.
