## ADDED Requirements

### Requirement: A cross-tab block shows two questions against each other
The system SHALL let an editor add a block that names two different choice-type questions of the
report's home survey, and SHALL show the table computed by the Data module for them with the
report's K: masked cells and withheld totals as computed, never recomputed in the report.

#### Scenario: Adding a cross-tab
- **WHEN** an editor adds a cross-tab of the transport question by the age question
- **THEN** the report's page shows a table with the transport choices in rows and the age choices in columns

#### Scenario: A small group
- **WHEN** one respondent gave a pair of answers and the report's K is 3
- **THEN** the page shows "<3" in that cell and no payload of the page carries the number 1 for it

#### Scenario: The report's own K
- **WHEN** the report's K is set to 1
- **THEN** the same cell shows 1

#### Scenario: The view is listed in Data
- **WHEN** a cross-tab block was added
- **THEN** the survey's responses dataset lists a cross-tab view, and that view cannot be deleted while the block shows it

#### Scenario: The same question twice
- **WHEN** an editor adds a cross-tab naming one question for rows and columns
- **THEN** the block is refused with a message

### Requirement: An engagement block shows who took part
The system SHALL let an editor add a block showing how many people opened the home survey, answered
and finished, with the series over time, as computed by the Data module.

#### Scenario: The three steps
- **WHEN** a survey has 6 clean sessions of which 4 answered and 3 finished, and an engagement block is added
- **THEN** the page shows 6 opened, 4 answered and 3 finished

### Requirement: The author of a report may show the marks of a map block
The system SHALL show a map block as a grid of counts unless the report's editor switched "Show the
marks themselves" on for that block; then the block SHALL carry the geometry of every mark of clean,
non-empty sessions and nothing else — no identifier, no session, no answer to a sub-question.

#### Scenario: Off by default
- **WHEN** a map block is added
- **THEN** its page payload holds cells and no mark

#### Scenario: Switched on
- **WHEN** an editor switches the marks on for a block of a point question with 5 points
- **THEN** the page payload holds 5 point geometries with empty properties, and no cell

#### Scenario: Switched off again
- **WHEN** the editor switches it off
- **THEN** the payload holds cells again

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
