# Paper versus artifact comparison

`SC26_paper_vs_artifact.pdf` contains one page for each computational paper
figure. The paper plot is on top and the corresponding artifact output is
below it. Every page states whether the displayed output is a plot from
committed inputs or uses an NSYS-derived result.

The comparison builder itself does not export NSYS files. For Figures 3 and
4, the raw NSYS validation results are stored separately from the paper-style
plots. Figure 5 uses the selected NSYS-derived Composite result; its raw trace
entry point is `pipeline/reproduce_fig5_from_nsys.sh`, which regenerates the
Monolithic baseline rather than that committed Composite curve. The standard
Figure 6 full tasks start from committed trace-derived metadata.

Rebuild it from the current paper PDF with:

```bash
.venv/bin/python scripts/make_paper_reproduction_comparison.py \
  --paper /path/to/ProvisioningPaper.pdf
```

Ghostscript is required to render the source PDFs. The paper PDF itself is not
copied into the repository.
