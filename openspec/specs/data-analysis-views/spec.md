# data-analysis-views Specification

## Purpose
View kinds that compute something — engagement, cross-tab, coverage, density — in the Data module: what a dataset holds decides the kinds it takes, every count leaves masked under K and every map kind is a grid, the same for every reader. Reports render these results and compute nothing. Implementation: `data/analysis.py`, `data/dataviews.py`; tests `survey/tests/test_data_analysis_views.py`.
## Requirements
### Requirement: A view kind follows what its dataset holds
The system SHALL offer, for a dataset, only the view kinds its contents allow: `objects` for a
layer of objects; `grid` for the answers to any map question, `coverage` when that question draws
lines or areas, `density` when it places points or spray; `engagement`, `crosstab` and `responses`
for a survey's responses. A view of a kind the dataset does not allow SHALL be refused on every
surface.

#### Scenario: Coverage of a line question
- **WHEN** an editor creates a coverage view on the answers dataset of a line question
- **THEN** the view is saved with kind `coverage`

#### Scenario: Coverage of a point question
- **WHEN** an editor posts a coverage view on the answers dataset of a point question
- **THEN** the view is refused and names the kinds the dataset allows

#### Scenario: A cross-tab on a layer
- **WHEN** a client posts a cross-tab view on a layer dataset
- **THEN** the view is refused

### Requirement: An engagement view counts opened, answered and finished
The system SHALL compute, for an engagement view, the number of clean sessions opened, those with
at least one answer and those completed, for the whole survey family and per period of collection
(days up to 45 days, weeks up to 53 weeks, months beyond), and SHALL mask every count greater than
zero and under K.

#### Scenario: The three steps
- **WHEN** a survey has 6 clean sessions of which 4 hold an answer and 3 are completed, and K is 3
- **THEN** the view's steps read opened 6, answered 4, finished 3

#### Scenario: Moderated and trashed sessions do not count
- **WHEN** one more session is on hold and another is in the trash
- **THEN** the steps do not change

#### Scenario: A quiet day is masked
- **WHEN** one of the days of collection has a single opened session and K is 3
- **THEN** that day's opened count shows as "<3" and carries no value

### Requirement: A cross-tab view counts distinct respondents for two questions
The system SHALL compute, for a cross-tab view naming two different top-level questions of type
choice, multiple choice, rating or thumbs by their codes, the number of distinct respondents per
pair of choices among the clean, non-empty sessions that answered both, across the survey's
versions. A cell greater than zero and under K SHALL be masked; the total of every row and column
holding a masked cell, and the number of respondents who answered both, SHALL then be withheld, so
that no masked value can be worked out from the totals.

#### Scenario: Counts per pair
- **WHEN** 4 respondents answered "Car" and "Under 30", 3 answered "Bike" and "Over 60", and K is 3
- **THEN** the table shows 4 and 3 in those cells and 0 elsewhere

#### Scenario: A small cell is masked and its margins withheld
- **WHEN** one respondent answered "Bike" and "Under 30" and K is 3
- **THEN** that cell shows "<3" with no value, and the totals of its row and column and the number who answered both are withheld

#### Scenario: A question that is not a choice
- **WHEN** a cross-tab view names a free-text question
- **THEN** the view is refused naming the question

#### Scenario: The question was replaced by publishing
- **WHEN** unpublished changes are published after the view was saved
- **THEN** the view still computes, counting the answers of every version

### Requirement: Coverage and density views are grids
The system SHALL compute coverage and density views on the same adaptive grid as a grid view, with
cells holding fewer than K respondents omitted. A coverage cell SHALL carry the distinct
respondents whose line or area reaches it and their share of all respondents who drew; a density
cell SHALL carry the number of points or spray dots inside it. No answer's own geometry SHALL
leave.

#### Scenario: Overlapping areas
- **WHEN** 4 respondents each drew an area over the park, a fifth drew one elsewhere, and K is 3
- **THEN** the coverage view holds cells over the park with 4 respondents and a share of 0.8, and none elsewhere

#### Scenario: Several marks from one respondent
- **WHEN** 3 respondents placed 7 points between them in one cell and K is 3
- **THEN** the density view's cell says 7 marks and 3 respondents

#### Scenario: Many marks from too few people
- **WHEN** 2 respondents placed 20 points in one cell and K is 3
- **THEN** the density view holds no cell there

### Requirement: An analysis view is read the same on every surface
The system SHALL return an analysis view's result — masked and gridded as above, with the K it
used — to the dataset page's preview, REST API v1 and the MCP server alike, and SHALL NOT offer an
unmasked reading of a view to any role.

#### Scenario: The owner reads a cross-tab over the API
- **WHEN** the workspace owner reads a cross-tab view's data with a token
- **THEN** a cell under K comes back masked, as it would on a public page

#### Scenario: Preview on the dataset page
- **WHEN** an editor opens a cross-tab view from the dataset page
- **THEN** the page shows the table with its masked cells and says how many respondents answered both questions

