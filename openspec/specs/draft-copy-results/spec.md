# draft-copy-results Specification

## Purpose
TBD - created by archiving change draft-results-scope. Update Purpose after archive.
## Requirements
### Requirement: A draft copy reports its published survey's responses

A draft copy SHALL resolve to the version family of the survey it was made from, on every
creator-facing surface that reports responses: the analytics dashboard, its table/map/chart
partials, the violations panel, and the data export. The default scope on a draft SHALL be that
whole family.

#### Scenario: Results on a draft show the published responses

- **WHEN** a creator opens Results on a draft copy of a survey that has collected responses
- **THEN** the reported response count is the published family's, not the draft's

#### Scenario: A draft's own test sessions are not in the default scope

- **WHEN** a draft copy has test sessions from previewing it, and its Results is opened with no
  `version` parameter
- **THEN** those test sessions are not reported

#### Scenario: The export follows the same scope

- **WHEN** data is downloaded from a draft copy with no `version` parameter
- **THEN** the export contains the published family's responses

### Requirement: The version filter accepts a draft scope

The `version` filter SHALL accept the value `draft`, resolving to the family's draft copy alone. The
value SHALL be offered in the version picker whenever the family has a draft copy, from the draft's
Results and from the canonical survey's Results alike.

#### Scenario: Selecting the draft scope shows test sessions

- **WHEN** `version=draft` is requested on a family that has a draft copy
- **THEN** only the draft copy's sessions are reported

#### Scenario: The picker offers the draft on a single-version survey

- **WHEN** a survey with no archived versions has a draft copy
- **THEN** the version picker renders and offers both the current version and the draft

#### Scenario: The draft scope is never the default

- **WHEN** Results is opened with no `version` parameter on a family that has a draft copy
- **THEN** the selected scope is the whole family

#### Scenario: `draft` with no draft copy falls back

- **WHEN** `version=draft` is requested on a family that has no draft copy
- **THEN** the whole family is reported

### Requirement: Question columns report draft answers under the draft scope

Under the draft scope, question aggregation SHALL include the draft copy's questions in the lineage
that carries their code and input type, so answers given while previewing a draft report against the
same columns as the published answers.

#### Scenario: A cloned question reports its draft answers

- **WHEN** `version=draft` is requested and the draft's test sessions answered a question cloned
  from the published survey
- **THEN** those answers are reported under that question

#### Scenario: A question added only in the draft is reported

- **WHEN** `version=draft` is requested and the draft added a question that the published survey
  does not have
- **THEN** that question is reported with its draft answers

### Requirement: Draft sessions are actionable when in scope

Session-level actions on the analytics surface SHALL accept sessions belonging to the family's draft
copy: open, edit an answer, set tags, set validation status, trash, restore, hard delete, and their
bulk forms. Sessions outside the family and its draft SHALL still be rejected.

#### Scenario: A draft test session opens

- **WHEN** a creator opens a session listed under the draft scope
- **THEN** the session detail is shown

#### Scenario: A foreign session is still rejected

- **WHEN** a session id belonging to an unrelated survey is requested on this survey's analytics
- **THEN** the request is rejected

### Requirement: Published results never include draft test data

The public results page SHALL build its aggregates from the canonical survey and its archived
versions only, never from a draft copy's sessions.

#### Scenario: A previewed draft does not change the public page

- **WHEN** a draft copy of a survey with a published results page accumulates test sessions
- **THEN** the public results page's aggregates are unchanged

