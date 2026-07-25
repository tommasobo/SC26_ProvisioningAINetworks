# Paper versus artifact comparison

`SC26_paper_vs_artifact.pdf` contains one page for each computational paper
figure. The paper plot is on top and the corresponding artifact output is
below it. Every page states whether the displayed output is a plot from
the full workflow or from numerical inputs supplied with the artifact.

After a full run, rebuild it from the current paper PDF with:

```bash
.venv/bin/python scripts/make_paper_reproduction_comparison.py \
  --paper /path/to/ProvisioningPaper.pdf \
  --artifact-figures /scratch/path/provisioning_artifact/figures \
  --run-manifest /scratch/path/provisioning_artifact/run_manifest.json
```

Ghostscript is required to render the source PDFs. The paper PDF itself is not
copied into the repository.
