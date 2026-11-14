## ADDED Requirements

### Requirement: Public surfaces read answers through one aggregation path
The system SHALL compute everything a public surface shows of answers — the public results page,
Site results blocks, and later report embeds and open-data pages — through `data.aggregate`: one
masking rule (a count greater than zero and smaller than K displays as "<K" with no exact value in
the payload) and one grid. API and MCP reads, which require a workspace role, SHALL keep exact
numbers.

#### Scenario: Small bucket masked on every public surface
- **WHEN** a choice option was picked by 2 respondents, K is 3, and the question is shown on the
  public results page and in a Site results block
- **THEN** both show "<3" and neither payload contains the number 2 for that option

#### Scenario: API keeps exact numbers
- **WHEN** an API client with a workspace role reads the response summary of the same survey
- **THEN** the option's count is 2

### Requirement: A public map never carries an individual geometry
A public map of a point, line, polygon or spray question SHALL be a grid of square cells: a point
counts in its cell, a spray cloud in every cell holding one of its dots, a line or polygon in every
cell it touches. Each cell SHALL count distinct respondents, and a cell with fewer than K
respondents SHALL be omitted from the payload, not masked, because its location is the sensitive
fact. The payload SHALL contain cell boxes and counts only — no answer geometry and no
identifiers.

#### Scenario: Points become cells
- **WHEN** 5 respondents placed points in one cell and 1 respondent placed a point far away, K = 3
- **THEN** the map payload holds one cell with 5 respondents and nothing for the lone point

#### Scenario: A polygon counts in every cell it touches, once per respondent
- **WHEN** 3 respondents drew polygons covering the same two cells and one of them drew two
  overlapping polygons
- **THEN** each of the two cells counts 3 respondents

#### Scenario: Frozen page with points refuses to show them
- **WHEN** a page was frozen with a snapshot of an earlier format that held point features
- **THEN** the page shows the "refresh needed" state to visitors instead of the points
