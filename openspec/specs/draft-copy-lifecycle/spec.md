# draft-copy-lifecycle Specification

## Purpose
TBD - created by archiving change draft-results-scope. Update Purpose after archive.
## Requirements
### Requirement: Discarding a draft copy succeeds regardless of test sessions

Discarding a draft copy SHALL delete the draft's own test sessions together with the draft header,
in one transaction, and SHALL then redirect to the canonical survey. A draft that has been previewed
SHALL be discardable.

#### Scenario: A previewed draft is discarded

- **WHEN** a draft copy that has test sessions is discarded
- **THEN** the draft, its sections and its test sessions are gone
- **AND** the creator is redirected to the canonical survey

#### Scenario: The canonical survey is untouched

- **WHEN** a draft copy with test sessions is discarded
- **THEN** the canonical survey's sessions, sections and version number are unchanged

#### Scenario: Discard is atomic

- **WHEN** deleting the draft header fails
- **THEN** its test sessions are not deleted either

