# Paper versus artifact comparison

`SC26_paper_vs_artifact.pdf` contains one page for each computational paper
figure. The paper plot is on top and the corresponding artifact output or
raw-derived result is below it. Each page states whether the lower plot is a
fresh result, a compact-data redraw, or a plot-only result.

Rebuild it from the current paper PDF with:

```bash
.venv/bin/python scripts/make_paper_reproduction_comparison.py \
  --paper /path/to/ProvisioningPaper.pdf
```

Ghostscript is required to render the source PDFs. The paper PDF itself is not
copied into the repository.
