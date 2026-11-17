## ADDED Requirements

### Requirement: The report is the editor's canvas
The report editor SHALL show the report as its readers see it in the centre of the page, an
outline of its blocks on the left and one context panel on the right. The context panel SHALL
show the settings of the selected block, and the report's settings when no block is selected. The
editor SHALL NOT show the report in a separate preview frame. The same builder SHALL open at the
report's own address and through its home survey's Public results tab.

#### Scenario: Opening a report
- **WHEN** an editor opens a report with a heading and a key-numbers block
- **THEN** the page shows both blocks with the report's opening above them, the outline lists them, and the panel shows the report's settings

#### Scenario: A block is selected by its address
- **WHEN** the editor is opened with `?block=<id>` of one of its blocks
- **THEN** that block is marked selected and its settings are the visible pane of the panel

#### Scenario: A viewer or a plan without Reports
- **WHEN** the report is opened by someone who may read but not write it
- **THEN** the canvas shows the report without editing controls and the panel's fields are disabled

### Requirement: Words are written on the page
The system SHALL let an editor change, on the canvas itself, the report's opening (line above the
title, title, opening paragraph), a heading, a text block, the rows of a key-numbers or quotes
block, a picture's file and caption, a map's description and a block's title, and SHALL save each
change without a Save button. The answer to such a save SHALL carry the block as it is now drawn,
its outline row and its settings pane.

#### Scenario: Key numbers row by row
- **WHEN** the builder saves a key-numbers block with the rows "447 / residents answered" and "77 / paper questionnaires"
- **THEN** the block holds those two numbers in that order and the answer's block fragment shows them

#### Scenario: A question block's title left alone
- **WHEN** the builder saves a chart block whose title on the page was never typed
- **THEN** the block keeps no title of its own and readers see the question's name

#### Scenario: The opening
- **WHEN** the builder saves the opening with a new title
- **THEN** the report's title is the new one and the answer carries the opening as it is now drawn

### Requirement: Blocks are added from a library, where they are wanted
The system SHALL offer one block library, opened by "Add block" and by the "+" between two
blocks, in which a story block is added with one click and a chart or a map with one click on its
question. A block added from a "+" SHALL be placed at that position. A picture block SHALL be
addable without a file and SHALL NOT be shown to readers until it has one.

#### Scenario: A block between two others
- **WHEN** an editor adds a text block after the first of three blocks
- **THEN** the report's blocks are the first, the new text block, then the other two, and the editor opens with the new block selected

#### Scenario: A question's chart in one click
- **WHEN** an editor picks a choice question in the library
- **THEN** a chart block of that question is added

#### Scenario: A picture block without a picture
- **WHEN** an editor adds a picture block and uploads nothing
- **THEN** the block exists, the canvas offers to drop a file on it, and the report's page does not show it

### Requirement: A block readers do not see says why
The canvas SHALL keep a block that readers do not see — hidden by the author, not filled in, or
about a question that no longer exists — and SHALL say which of the three it is.

#### Scenario: A hidden block
- **WHEN** a text block is marked hidden
- **THEN** the canvas shows it with a note that readers do not see it, and the report's page leaves it out

#### Scenario: An empty quotes block
- **WHEN** a quotes block has no quote
- **THEN** the canvas shows it with a note that it is left out until it has one

## MODIFIED Requirements

### Requirement: A block's row names its type
In the editor's outline a block's row SHALL show the name of its type in the interface language under the block's title, and SHALL NOT show the type's internal key. A row whose title is the type's name, because the block has no title of its own, SHALL show the name once.

#### Scenario: A titled block
- **WHEN** an editor whose interface is German opens a report with a Key numbers block titled "Who took part"
- **THEN** the block's row reads "Who took part" with "Kennzahlen" under it, and nowhere "numbers"

#### Scenario: A block with no title of its own
- **WHEN** the report has a Quotes block without a title
- **THEN** its row reads the type's name once
