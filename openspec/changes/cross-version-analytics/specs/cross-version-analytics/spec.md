# cross-version-analytics

## ADDED Requirements

### Requirement: Response aggregation spans the version family
Creator-facing response counts and analytics SHALL aggregate sessions across the
canonical survey and all of its version copies (the "family") by default. Publishing a
new version MUST NOT reduce any displayed response count. Each session belongs to
exactly one version header, so family aggregation MUST count every session exactly once.

#### Scenario: Counts survive publishing a new version
- **GIVEN** a survey with 340 sessions collected on v2
- **WHEN** the creator publishes v3 (sessions move to the archived v2 header)
- **THEN** the dashboard card and the Results space still report 340 started

#### Scenario: Version filter isolates a single version
- **WHEN** the creator selects "v3" in the Results version filter
- **THEN** only sessions attached to the v3 header are shown
- **AND** selecting "All versions" restores the family-wide view

### Requirement: Questions aggregate by lineage
Answers SHALL be aggregated per question lineage — questions sharing a `code` and
`input_type` within the family. A changed `input_type` MUST break the lineage so answers
of incompatible shapes are never merged. Lineages with no question in the canonical
version SHALL be presented in an "Archived questions" group labeled with their version
range instead of being hidden.

#### Scenario: Compatible edit keeps one lineage
- **GIVEN** question Q5 (`choice`) present in v2 and, as a clone with a new id, in v3
- **WHEN** All-versions analytics renders Q5
- **THEN** answers from both versions are combined in one lineage

#### Scenario: Type change splits the lineage
- **GIVEN** Q5 was `text` in v2 and is `choice` in v3
- **WHEN** All-versions analytics renders
- **THEN** two separate entries appear, the archived one labeled with its version range

#### Scenario: Deleted question is archived, not hidden
- **GIVEN** Q7 existed in v2 with answers and was removed in v3
- **WHEN** All-versions analytics renders
- **THEN** Q7 appears in the "Archived questions" group with its historical answers

#### Scenario: Removed choice code is flagged, never merged
- **GIVEN** choice code 4 was answered in v2 and removed from the choice set in v3
- **WHEN** the lineage's distribution renders
- **THEN** code 4 appears as a "no longer offered" bucket with its historical count

### Requirement: Public results blocks resolve answers by lineage
Chart and map blocks on the public results page SHALL resolve answers through the
question lineage across the whole family, regardless of whether the block's question FK
points at a current or an archived question object. Publishing a new version MUST NOT
stop a published block from counting new responses.

#### Scenario: Block keeps counting after publish
- **GIVEN** a published results block bound to a v2 question object
- **WHEN** v3 is published and new respondents answer the cloned question
- **THEN** the block's counts include both v2 and v3 answers

### Requirement: Choice codes are never silently reused
The editor SHALL allocate new choice codes above every code historically answered within
the lineage, and MUST reject manually assigning a historically answered code to a choice
with a different meaning. This keeps cross-version aggregation by code sound.

#### Scenario: New choice gets a fresh code
- **GIVEN** codes 1–4 were answered in earlier versions and the current set is 1–3
- **WHEN** the creator adds a new choice
- **THEN** it is assigned code 5, not 4

### Requirement: Publish dialog explains analytics continuity
The publish and force-publish confirmations SHALL state that existing responses remain
visible under All versions, and that breaking changes move affected questions to the
Archived group — before the creator commits to publishing.

#### Scenario: Force publish explains where answers go
- **WHEN** the creator force-publishes a draft with breaking changes
- **THEN** the confirmation explains the affected answers stay accessible in
  All-versions analytics under Archived questions
