# SC26 AD/AE compliance report

Checked on 24 July 2026 against the current SC26 AD/AE requirements and the
official `sc26-repro` author template.

## Result

`ad_ae_appendix.tex` uses the official `IEEEtran.cls` and `sc26repro.sty`
files without changes. The explanation and example tags are commented out,
all appendix text is black, and no author or affiliation block was added.

## Requirements check

| Requirement | Status |
|---|---|
| Paper contributions are listed | Pass |
| Artifacts are mapped to contributions and paper elements | Pass |
| Relation, expected results, time, setup, execution, and analysis are provided for each artifact | Pass |
| AE follows AD in the same appendix | Pass |
| Local and Slurm instructions are included | Pass |
| Optional high-cost work is clearly gated | Pass |
| Requested badges are stated | Pass |
| Official template is used with example text removed | Pass |

## Remaining submission actions

1. Select the requested badges in the SC26 submission form.
2. Assign the persistent DOI at the artifact-freeze stage.
3. Create the final archive only after the public repository has been
   reviewed.

No DOI, archive, or release was created while preparing this branch.

## Build verification

The PDF was built successfully with Tectonic 0.16.9. The source uses only the
official class and template style. The build produced no TeX errors,
undefined controls, or overfull boxes. The included Makefile retains the
standard three-pass `pdflatex` build for a TeX Live environment.
