# public-aggregates Specification

## Purpose
What a public surface may show of answers — one masking rule and one grid (`data.aggregate`) for the public results page, Site results blocks and later report embeds and open-data pages; a public map never carries an individual geometry. Exact numbers stay inside the workspace (Responses, export, API, MCP). Implementation: `data/aggregate.py`; tests `survey/tests/test_public_aggregates.py`.
## Requirements
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
identifiers. The cell size SHALL be the finest of 40, 20, 10 and 5 cells across the answers' extent
(never under 20 m) that shows at least 60 % of the respondents, else the one showing the most. When
respondents are left out, the page SHALL say so: a map with no cell SHALL be replaced by a note
explaining that areas with fewer than K people stay hidden, and a map with hidden respondents SHALL
name how many in its caption.

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

#### Scenario: A small survey gets coarser cells
- **WHEN** 6 respondents placed points a few hundred metres apart across a town, K = 3, so that no
  cell of a 40-across grid holds 3 of them
- **THEN** the map uses a coarser grid whose cells hold them and shows those cells

#### Scenario: Too few answers to show anyone
- **WHEN** 2 respondents placed points far apart, K = 3
- **THEN** the payload holds no cell and a note, and the page shows the note instead of a map

### Requirement: The grid counts marks as well as respondents
The grid SHALL report, for every cell it shows, the number of marks inside it: each point, and each
dot of a spray cloud, that falls in the cell. A line or polygon SHALL count as one mark in every
cell it touches. Whether a cell is shown SHALL still depend only on its number of distinct
respondents.

#### Scenario: Two points from one respondent
- **WHEN** 3 respondents placed points in one cell, one of them two points, and K = 3
- **THEN** the cell reports 3 respondents and 4 marks

#### Scenario: Marks do not unlock a cell
- **WHEN** 2 respondents placed 10 points in one cell and K = 3
- **THEN** the cell is omitted

