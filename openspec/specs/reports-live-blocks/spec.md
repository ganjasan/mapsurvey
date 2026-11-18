# reports-live-blocks Specification

## Purpose
Report blocks that follow the data: a cross-tab and an engagement block over the Data module's analysis views, a map block that shows the marks themselves when its author says so, and tokens in the text that are filled from the home survey. Implementation: `reports/render.py`, `reports/services.py`, `reports/tokens.py`; tests `survey/tests/test_reports_live_blocks.py`.
## Requirements
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

### Requirement: An engagement block shows who took part
The system SHALL let an editor add a block showing how many people opened the home survey, answered
and finished, with the series over time, as computed by the Data module.

#### Scenario: The three steps
- **WHEN** a survey has 6 clean sessions of which 4 answered and 3 finished, and an engagement block is added
- **THEN** the page shows 6 opened, 4 answered and 3 finished

### Requirement: The author of a report may show the marks of a map block
The system SHALL build a map block from areas that count respondents unless the report's editor
switched "Use every mark" on for that block; then the block SHALL carry the geometry of every mark
of clean, non-empty sessions and nothing else — no identifier, no session, no answer to a
sub-question. Picking the Marks view SHALL switch it on, and switching it off while the marks are
shown SHALL return the block to a view built from areas.

#### Scenario: Off by default
- **WHEN** a map block is added
- **THEN** its page payload holds cells and no mark

#### Scenario: Switched on
- **WHEN** an editor switches the marks on for a block of a point question with 5 points
- **THEN** the page payload holds 5 point geometries with empty properties, and no cell

#### Scenario: Switched off again
- **WHEN** the editor switches it off
- **THEN** the payload holds cells again

#### Scenario: The Marks view
- **WHEN** an editor picks the Marks view of a block whose switch is off
- **THEN** the payload holds every mark, and publishing the report asks the author to confirm

### Requirement: Numbers in the text may follow the data
The system SHALL replace the tokens `{responses}`, `{opened}`, `{finished}`, `{marks:CODE}` and
`{respondents:CODE}` in a Text block, a key number and the opening paragraph with the home survey's
counts when the page is rendered, masked under the report's K; SHALL keep the values of the day a
report was frozen; and SHALL leave a token it cannot fill as written.

#### Scenario: A live number
- **WHEN** a Text block says "{responses} residents answered" and 4 people have answered
- **THEN** the page says "4 residents answered", and "5 residents answered" after one more answer

#### Scenario: A frozen report
- **WHEN** the report is frozen at 4 answers and a fifth arrives
- **THEN** the page still says "4 residents answered"

#### Scenario: Marks of a question
- **WHEN** a key number is "{marks:SPOT}" and residents placed 7 points on question SPOT
- **THEN** the page shows 7

#### Scenario: A count under K
- **WHEN** a token counts 2 and the report's K is 3
- **THEN** the page shows "<3"

#### Scenario: A token that cannot be filled
- **WHEN** a Text block of a report without a home survey says "{responses}", or names an unknown question code
- **THEN** the page shows the token as written

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

### Requirement: A map block is drawn the way its author chooses
A map block SHALL be drawn as one of `heat` (shading, darker where more people marked), `hotspots`
(a point question's numbered places, largest first, listed under the map with their respondents and
marks), `squares` or `marks`. A new block SHALL start as heat; a block without display settings
SHALL stay squares, or marks when its switch was on. A hot spot SHALL hold at least two marks and at
least K distinct respondents, or two marks alone when the author uses every mark; places below that
SHALL appear nowhere in the payload unless the author uses every mark. Hot spots SHALL be computed
by the Data module. The page, the PDF, the PNG and the CSV SHALL draw the same payload, and the
report file SHALL carry the view.

#### Scenario: A new map
- **WHEN** an editor adds the map block of a point question
- **THEN** it is drawn as heat from cells that count respondents

#### Scenario: Hot spots under K
- **WHEN** three people marked one corner, one person another place, K is 3 and the editor picks Hot spots
- **THEN** one spot is numbered with 3 respondents and 3 marks, and the lone mark is not in the payload

#### Scenario: Hot spots of every mark
- **WHEN** two people marked a third place and the editor switches "Use every mark" on
- **THEN** that place is numbered too

#### Scenario: A line question
- **WHEN** Hot spots is asked for the map of a line question
- **THEN** the block is drawn as heat

#### Scenario: A block made before
- **WHEN** a map block has no display settings
- **THEN** it is drawn as squares

#### Scenario: A copy of the report
- **WHEN** a report with a map drawn as hot spots is copied
- **THEN** the copy's map is drawn as hot spots

### Requirement: The author frames a map block
The editor SHALL be able to keep the part of the map shown on the canvas as the block's frame, and
to clear it; a block with a frame SHALL open on that part for readers and in the PDF, and a block
without one on everything there is to draw. A frame that is not a west–south–east–north box SHALL be
ignored.

#### Scenario: Keeping a view
- **WHEN** the editor keeps a view of the map
- **THEN** the block's payload carries that frame and a copy of the report keeps it

#### Scenario: Clearing it
- **WHEN** the editor chooses to show all the answers
- **THEN** the payload carries no frame

#### Scenario: Nonsense
- **WHEN** a frame whose east is west of its west is posted
- **THEN** the block has no frame

### Requirement: A map block shows several questions as layers
A map block SHALL be able to show, beside its own question, up to three other map questions of the
report's workspace on the same map, each named by its survey and question code. The block's own
question SHALL be drawn on top. A layer SHALL be refused when it names a question that is not a map
question, a question of another workspace, the block's own question, or a question the block
already shows. A layer whose survey or question no longer exists SHALL be left out of the page. The
report file SHALL carry the layers, and a copy of the report onto another survey SHALL read that
survey in every layer.

#### Scenario: Adding a layer
- **WHEN** an editor adds another map question of the survey to a map block
- **THEN** the page payload carries that question as a second layer in a colour of its own

#### Scenario: Removing a layer
- **WHEN** the editor removes the layer
- **THEN** the block is a map of one layer again

#### Scenario: Not a map question
- **WHEN** a choice question, the block's own question or a question of another workspace is posted as a layer
- **THEN** no layer is added

#### Scenario: The next round
- **WHEN** a report with a map of two layers is copied onto a survey that has both questions
- **THEN** the copy's second layer names that survey

### Requirement: Each layer of a map is drawn with its own view and settings
Every layer of a map block SHALL have its own view (`heat`, `hotspots` for a point question,
`squares`, `marks`), colour, name in the legend, and settings of the view: for heat its spread and
strength; for hot spots how many are numbered (5, 10 or all), what counts as one place (60, 120 or
300 m), whether the places are listed under the map and whether shading is drawn under the numbers;
for squares automatic, finer or coarser cells; for marks their size and whether they are opaque.
Each layer SHALL be built from areas with at least K respondents unless its own "Use every mark"
switch is on, and a layer with the switch on SHALL be listed before publishing and need the
author's confirmation. Settings equal to the defaults SHALL not be stored.

#### Scenario: A layer drawn its own way
- **WHEN** the editor draws the second layer as hot spots of 300 m places in another colour and name
- **THEN** that layer carries its spots, colour and name, and the block's own layer is unchanged

#### Scenario: Marks of one layer
- **WHEN** "Use every mark" is switched on for the second layer only
- **THEN** that layer carries every mark, the first none, and publishing asks the author to confirm

#### Scenario: View settings
- **WHEN** the editor sets a wide spread and strength 5 for a heat layer
- **THEN** the payload carries them and the block stores only those two settings

### Requirement: A map of several layers has a legend
A map block of more than one layer SHALL show a legend under the map naming each layer in its
colour, unless the author switched the legend off; a layer drawn as hot spots with its list on SHALL
have its places listed under the layer's name. When the author lets readers switch layers, the
legend SHALL carry a box per layer that turns it off and on, whether or not the legend was switched
off.

#### Scenario: The legend
- **WHEN** a reader opens a report with a map of two layers
- **THEN** the page names both layers under the map

#### Scenario: Readers switch layers
- **WHEN** the author lets readers switch layers
- **THEN** each row of the legend has a box for its layer

