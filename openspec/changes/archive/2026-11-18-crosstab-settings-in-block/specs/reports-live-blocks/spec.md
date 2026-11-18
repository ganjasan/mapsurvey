## MODIFIED Requirements

### Requirement: A cross-tab block shows two questions against each other
The system SHALL let an editor add a block that names two different choice-type questions of the
report's home survey, and SHALL show what the Data module computed for them with the report's K:
masked cells and withheld totals as computed, never recomputed in the report. The block library
SHALL add it in one click with the first two questions a cross-tab may name; the block's settings
SHALL change either question.

#### Scenario: Adding a cross-tab
- **WHEN** an editor clicks the Cross-tab tile of a survey with a transport and an age question
- **THEN** the report gets a cross-tab of the first by the second, drawn as bars, without a form in the library

#### Scenario: Changing the questions
- **WHEN** the editor sets the block's Split by to another question
- **THEN** the block shows the new pair, and a view the report had made for the old pair and nothing else shows is gone from Data

#### Scenario: A small group
- **WHEN** one respondent gave a pair of answers and the report's K is 3
- **THEN** the page shows "<3" for that pair and no payload of the page carries the number 1 for it

#### Scenario: The report's own K
- **WHEN** the report's K is set to 1
- **THEN** the same pair shows 1

#### Scenario: The view is listed in Data
- **WHEN** a cross-tab block was added
- **THEN** the survey's responses dataset lists a cross-tab view, and that view cannot be deleted while the block shows it

#### Scenario: The same question twice
- **WHEN** an editor sets a cross-tab's Question and Split by to one question
- **THEN** the change is refused with a message and the block keeps its pair

## ADDED Requirements

### Requirement: A cross-tab is drawn the way its author chooses
A cross-tab block SHALL be drawn as one of `bars` (for each option of the Question, a bar per group
of Split by), `stacked` (for each option, its people split by group, 100 % wide), `ranking` (the
options by how many chose them) or `table`, with values as a share of the group's respondents or
as counts, and optionally sorted by value. A share SHALL be a count divided by a total the Data
module published; a group whose total is withheld SHALL be left out of the bars and named in a note
under them. A block made before these settings SHALL keep the table. The PDF, the PNG and the CSV
SHALL keep the table.

#### Scenario: Bars as shares
- **WHEN** 4 of the 10 people under 35 and 9 of the 12 people over 64 chose "Safer crossings"
- **THEN** the bars read 40 % and 75 % for that option

#### Scenario: A group that cannot be a share
- **WHEN** a group of Split by has a cell under K, so its total is withheld
- **THEN** that group has no bars and the note under the chart names it

#### Scenario: Counts, sorted
- **WHEN** the author picks Count and Sort by value
- **THEN** the options are ordered by how many chose them and the bars show counts
