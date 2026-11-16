## ADDED Requirements

### Requirement: A report can be copied onto another survey
The system SHALL let an editor copy a report onto another survey of the workspace. The copy SHALL
keep the opening, the written blocks, the order and each block's settings, SHALL have the chosen
survey as its home, SHALL point every data block at that survey by matching the question code, and
SHALL be unpublished and visible to the workspace only.

#### Scenario: A second round with the same codes
- **WHEN** an editor copies a report with a text block, a chart of `PRIO` and an engagement block onto a second survey that has a question `PRIO`
- **THEN** the copy has the same three blocks in the same order, its chart and engagement blocks read the second survey, and its page shows the second survey's numbers

#### Scenario: Copying without choosing a survey
- **WHEN** an editor copies a report without choosing a survey
- **THEN** the copy's data blocks read the same surveys as the original's

### Requirement: Blocks that cannot be rebound are named
The system SHALL keep, in place of a data block whose question the chosen survey does not have, a
hidden block that says what the original showed, and SHALL tell the author after the copy which
blocks those are. Nothing SHALL be dropped silently.

#### Scenario: A question the second round lacks
- **WHEN** an editor copies a report with charts of `PRIO` and `AGE` onto a survey that has `PRIO` only
- **THEN** the copy has a chart of `PRIO` and, in the place of the `AGE` chart, a hidden block naming it; the message after the copy names the `AGE` block; the copy's page shows no trace of it

### Requirement: A Compare block shows one question in two rounds
The system SHALL offer a block that shows, for one question code present in two surveys of the
workspace, the share of each answer in both, with the number of people who answered in each. A
group smaller than the report's threshold SHALL be masked in its own round. The block SHALL be
refused when the other survey has no question with that code and a comparable type.

#### Scenario: Two rounds side by side
- **WHEN** an editor adds a Compare block of `PRIO` with a second survey where the answers differ
- **THEN** the page shows both surveys' names, how many people answered in each, and each option's share in each

#### Scenario: Small groups
- **WHEN** an option was chosen by fewer people than the threshold in one round
- **THEN** that round's cell reads "<K" with no share, and the other round's cell is shown

#### Scenario: No such question in the other survey
- **WHEN** an editor adds a Compare block naming a survey without that question code
- **THEN** the block is refused with a message and nothing is added

### Requirement: Reuse is measured
The system SHALL emit `report_reused` when a report is copied, with ids and counts only.

#### Scenario: A copy onto another survey
- **WHEN** an editor copies a report onto another survey with one unmatched block
- **THEN** `report_reused` is emitted with `onto` true and `unmatched` 1
