# SC26 AD/AE compliance report

Checked on 24 July 2026 against:

- the official [SC26 AD/AE Appendices requirements](https://sc26.supercomputing.org/program/papers/ad-ae-appendices/)
- the official [SC26 AD/AE Process and Badges page](https://sc26.supercomputing.org/program/papers/reproducibility-appendices-badges/)
- the official [SC26 author template and guidelines](https://github.com/jennfshr/sc26-repro/tree/main/for-paper-authors), commit
  `b5195e67d9ad0b5d07e8b6840558c7251c73b3c0`

## Result

`ad_ae_appendix.tex` follows the current SC26 structure and compiles to the
five-page `ad_ae_appendix.pdf`. It uses the official `IEEEtran.cls` and
`sc26repro.sty` files without changes. The explanation and example tags are
commented out, all appendix text is black, and no author or affiliation block
was added.

The recommended evaluation path is within the SC26 eight-hour net review
budget. Expensive experiments are not part of that path. The appendix makes
the compact-data redraw, bounded fresh checks, Slurm path, and explicitly
enabled expensive path distinct.

## Requirements check

| SC26 requirement | Status | Where addressed |
|---|---|---|
| AD overview lists the paper contributions | Pass | AD, Section I-A |
| AD maps artifacts to contributions and paper elements | Pass | AD, Section I-B table |
| Each artifact explains its relation to the contributions | Pass | `Relation To Contributions` for A1 and A2 |
| Each artifact states expected results and how they support the paper | Pass | `Expected Results` for A1 and A2 |
| Reproduction time separates setup, execution, and analysis | Pass | `Expected Reproduction Time` for A1 and A2 |
| Setup covers hardware, versioned software with URLs, data, installation, and deployment | Pass | `Artifact Setup` for A1 and A2 |
| Execution describes tasks, dependencies, parameters, and repetitions | Pass | `Artifact Execution` for A1 |
| Analysis states outputs and how to evaluate them | Pass | `Artifact Analysis` for A1 and A2 |
| AE follows the AD in the same appendix | Pass | `Artifact Evaluation (AE)` begins on a new page |
| AE gives setup, execution, and analysis instructions for every AD artifact | Pass | AE artifacts A1 and A2 |
| AE does more than direct the reviewer to a wrapper script | Pass | The quick, local, Slurm, trace replay, task dependencies, outputs, and checks are described |
| Recommended AE work fits the eight-hour budget | Pass | Quick path plus bounded full path; Grok 4k is excluded |
| Special hardware and high-cost work are identified | Pass | Hardware sections and `--expensive_run` discussion |
| The AD states the intended badge request | Pass | Artifacts Available, Artifacts Evaluated-Functional, and Results Reproduced are named |
| Submission uses the official template with example text removed | Pass | Official class/style; both `usetag` lines remain commented |

The official process states that the AD is mandatory, the AE is optional for
accepted papers seeking badges, and the AE must appear after the AD in the same
appendix. It also allocates eight net hours to the evaluation. These points are
documented on the [SC26 process page](https://sc26.supercomputing.org/program/papers/reproducibility-appendices-badges/).

## Corrections made from the previous appendix

1. Added the missing AE section for both A1 and A2.
2. Changed the title from AD-only to the combined AD/AE title.
3. Added complete local, Slurm, analysis, and output-check instructions.
4. Referenced the final `artifact_freeze` branch and the final
   `reproduce_quick.sh` and `reproduce_full.sh` entry points.
5. Documented every full-script option relevant to reviewers and the hard
   `--expensive_run` gate.
6. Corrected the Python requirement to 3.10 or later and distinguished the
   quick requirements from `requirements-dev.txt`, which the full workflow
   needs.
7. Added URLs for all required software packages.
8. Replaced the invalid example `grok3/` and `llama3_3_n32/` download paths
   with a currently reachable public Grok trace path.
9. Replaced the A2 statement that no reproduction time applies with separate
   setup, execution, and analysis estimates.
10. Removed the claim that every generated figure is visually identical to
    the paper. The appendix now states the known Figure 5 and Figure 6
    differences and explains which plots use compact paper data.
11. Documented that the public N32/GPU128 Llama directory identifies a 7B
    model although the paper says 70B.
12. Documented that the public vLLM 70B workload is not a valid replacement
    for the recovered vLLM 8B paper input.
13. Kept Figures 1, 7, 8, 9, and 10 on the compact-data plotting path and
    retained plotting scripts for all reported figures.

## Remaining submission actions

These are administrative checks, not missing appendix content:

1. Push the final `artifact_freeze` branch and confirm that it is readable
   from a clean checkout before submitting the PDF.
2. Select the requested badges in the SC26 submission form. The appendix
   states the intended set, but the form controls the actual request.
3. Assign persistent DOI records by the SC26 artifact-freeze deadline, not
   before. The [SC26 process page](https://sc26.supercomputing.org/program/papers/reproducibility-appendices-badges/)
   lists 25 August 2026 as the artifact-freeze and DOI deadline. No DOI was
   created during this work.
4. If the submission system requests an archive, create it only after the
   user has reviewed the final branch. No archive or release was created here.

## Build verification

The PDF was built successfully with Tectonic 0.16.9 because `pdflatex` was not
installed in the current login environment. The source uses only the official
class and template style. The build produced no TeX errors, undefined controls,
or overfull boxes. The included Makefile retains the official three-pass
`pdflatex` build for a standard TeX Live environment.

The official template source was inspected in full, and the three older
appendices in `/users/btommaso/OldExamples` were used only as style references.
The final wording is concise, specific to this artifact, and avoids unsupported
claims.
