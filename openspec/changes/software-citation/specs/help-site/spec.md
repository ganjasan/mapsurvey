## ADDED Requirements

### Requirement: Citation reference page

The help site SHALL have a reference page at `reference/citing-mapsurvey/` titled "Citing Mapsurvey" that gives the reference to Mapsurvey in APA 7, Harvard, Chicago and BibTeX with the same author and title as `CITATION.cff`, a sentence researchers can use in a methods section, a link to `CITATION.cff` in the repository, and a section "Academic Pro" saying that students, researchers and non-profit research projects can use Pro free of charge in return for feedback and a citation, and how to ask for it.

#### Scenario: Page matches the citation file

- **WHEN** `help/src/content/docs/reference/citing-mapsurvey.md` and `CITATION.cff` are read
- **THEN** the page SHALL contain "Koniukhov, A." and the title "Mapsurvey" as the citation file names them
- **AND** it SHALL contain a BibTeX `@software` entry, a link to `CITATION.cff` and the heading "Academic Pro"
