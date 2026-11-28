## Why

Researchers who run a study on Mapsurvey ask how to cite it, and there is no answer: no `CITATION.cff`, no DOI, no help page. A citation in their papers is also what we ask for in return for Academic Pro (free Pro for students, researchers and non-profit research). Issue #789.

## What Changes

- `CITATION.cff` (CFF 1.2.0) at the repository root: title, author as in the README copyright (Artem Koniukhov), AGPL-3.0-only, site and repository URLs. GitHub shows it as "Cite this repository"; Zenodo reads it when a release is archived.
- Help page `reference/citing-mapsurvey/`: the reference in APA, Harvard, Chicago and BibTeX, a sentence for the methods section, and Academic Pro (what it is, what we ask in return, how to ask for it).
- A test keeps the help page and `CITATION.cff` naming the same author and title.

Not in this change: the Zenodo DOI. It needs the owner to connect the repository in Zenodo and a first GitHub release; the DOI is then added to both files in a follow-up.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `project-governance-docs`: gains the citation file.
- `help-site`: gains the citation reference page.

## Impact

- New files: `CITATION.cff`, `help/src/content/docs/reference/citing-mapsurvey.md`. One test in `survey/tests/test_help_site.py`. No product code, no migration.
