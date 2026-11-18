# reports-editor Specification

## Purpose
Editing a report on its own, with or without a home survey: a blank report, blocks, settings and publication at the report's address, the Reports list as the way in, deleting a report; editors of the workspace only. Implementation: `reports/editor_views.py`, `reports/views.py`; tests `survey/tests/test_reports_editor.py`.
## Requirements
### Requirement: A report is edited on its own
The system SHALL let an editor of a workspace create a blank report from the Reports list and edit
any report at its own address — settings, blocks, order, publication — whether or not it has a
home survey. A report with a home survey SHALL also need the editor role on that survey, and SHALL
stay editable through that survey's Public results tab.

#### Scenario: A blank report
- **WHEN** an editor presses "New report"
- **THEN** an unpublished, workspace-only report without a home survey opens in the editor

#### Scenario: Adding and writing a block by the report's address
- **WHEN** an editor adds a Key numbers block to a report without a home survey and enters two numbers
- **THEN** the block is saved and the report's page shows them

#### Scenario: A member of another workspace
- **WHEN** a member of another workspace opens the report's editor address
- **THEN** the answer is 404

#### Scenario: A viewer
- **WHEN** a member with the viewer role posts a block to the report
- **THEN** the answer is 404 and nothing is added

#### Scenario: The same report through its survey
- **WHEN** an editor adds a Text block on a survey's Public results tab
- **THEN** the block is on that survey's report, as it is when added at the report's own address

### Requirement: The Reports list opens the editor
The system SHALL link every report in the list to its editor for members who may edit, and SHALL
offer "New report" and "Import a report" to them only.

#### Scenario: A viewer's list
- **WHEN** a viewer opens the Reports list
- **THEN** reports are listed without editor links, and neither "New report" nor "Import a report" is offered

### Requirement: A report can be deleted
The system SHALL let an editor delete a report after the app's confirmation dialog has said what
goes with it, and SHALL leave the survey's answers untouched. The Delete action SHALL be offered on
the report's row in the Reports list and in the report's settings in the editor, for every report
the member may edit, whether or not the report has a home survey. It SHALL NOT be offered to a
member who may not edit the report. When the report is the one its survey's Public results tab
opens, the dialog SHALL say that the tab will open the survey's next report or start an empty one.
There SHALL be no separate confirmation page: opening the delete address deletes nothing.

#### Scenario: Deleting an imported report
- **WHEN** an editor presses Delete and confirms in the dialog
- **THEN** the report and its blocks are gone and the list no longer shows it

#### Scenario: Delete in the list
- **WHEN** an editor opens the Reports list
- **THEN** every report they may edit has a Delete action that asks through the dialog, naming the report and what goes

#### Scenario: A member who may not edit
- **WHEN** a viewer of the workspace opens the Reports list
- **THEN** no row offers Delete

#### Scenario: A report made from a survey
- **WHEN** an editor opens the settings of a report whose home is a survey
- **THEN** "Delete report…" is offered, and the dialog says what the survey's Public results tab will open afterwards

### Requirement: A block's row names its type
In the editor's outline a block's row SHALL show the name of its type in the interface language under the block's title, and SHALL NOT show the type's internal key. A row whose title is the type's name, because the block has no title of its own, SHALL show the name once.

#### Scenario: A titled block
- **WHEN** an editor whose interface is German opens a report with a Key numbers block titled "Who took part"
- **THEN** the block's row reads "Who took part" with "Kennzahlen" under it, and nowhere "numbers"

#### Scenario: A block with no title of its own
- **WHEN** the report has a Quotes block without a title
- **THEN** its row reads the type's name once

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
- **THEN** the canvas shows it with two actions, "Pick from answers" and "Write a quote", and a line that readers see nothing until it has one; no empty quote row

### Requirement: The editor's side panels can be resized
The outline and the context panel of the report editor SHALL be resizable by dragging their inner
edge, within limits that keep the canvas usable, and a double click on the edge SHALL restore the
default width. The chosen widths SHALL be remembered in the browser and applied the next time a
builder page opens; they SHALL NOT apply where the panel sits under the canvas on a narrow screen.

#### Scenario: Widening the settings panel
- **WHEN** an editor drags the left edge of the context panel to the left
- **THEN** the panel grows, the canvas narrows, and the width is kept after a reload

#### Scenario: Back to the default
- **WHEN** the editor double-clicks that edge
- **THEN** the panel returns to its default width

### Requirement: A start card shows its progress in place
On the page that starts a report, a pressed card SHALL show its busy state where the card's icon
is, without any element moving outside the card.

#### Scenario: Pressing a card
- **WHEN** a member presses "Blank report"
- **THEN** the card's icon becomes a spinner turning in place until the next page opens

### Requirement: One confirmation dialog across the creator app
Every confirmation a signed-in creator is asked for SHALL be the same dialog — a title, an optional
text, an optional muted note, Cancel and the action — on every creator page. A destructive action's
button SHALL be red and name the action; an action that destroys nothing SHALL use the primary
button. Creator pages SHALL NOT ask through the browser's own confirm box or a separate
confirmation page.

#### Scenario: A page outside the survey editor
- **WHEN** an owner presses "Remove" beside a member on the Members page
- **THEN** the app's dialog asks, not the browser's box

#### Scenario: An action that destroys nothing
- **WHEN** an owner presses "Switch billing period"
- **THEN** the dialog's action button is the primary one, not red

### Requirement: A block can come from any survey of the workspace
The system SHALL let the author choose, in the block library, the survey whose charts, maps,
cross-tab, engagement and comparison are offered, among the published surveys of the workspace the
member sees. The library SHALL start on the report's home survey; for a report without one it
SHALL start on the workspace's only such survey, and otherwise ask for a survey. Choosing another
survey SHALL NOT change the report's home survey.

#### Scenario: A blank report shows a chart
- **WHEN** an editor opens "Add block" in a report without a home survey, chooses a survey and picks one of its choice questions
- **THEN** the report has a chart of that question

#### Scenario: A second survey in the same report
- **WHEN** an editor of a report whose home survey is A chooses survey B in the library and picks one of B's questions
- **THEN** the report has a block reading B and its home survey is still A

#### Scenario: A survey of another workspace
- **WHEN** a block is posted with a survey of another workspace as its source
- **THEN** nothing is added

### Requirement: A report's home survey can be set, changed and cleared
The system SHALL make the survey of the first data block added to a report without a home survey
that report's home survey, when the author has the editor role on that survey. Report settings
SHALL show the home survey and let an editor set, change or clear it, offering only surveys the
member may edit; clearing SHALL keep every block. The "Take the survey" and "Link from the thanks
page" switches SHALL be shown only while the report has a home survey, and their stored values
SHALL survive a save made without them. A report somebody started SHALL NOT be filled with drafted
blocks by its survey's Public results tab.

#### Scenario: The first data block sets the home survey
- **WHEN** an editor adds a chart of a question of survey A to a report without a home survey
- **THEN** the report's home survey is A

#### Scenario: Setting it in settings
- **WHEN** an editor chooses survey A in the Survey card of Report settings
- **THEN** the report's home survey is A and the library offers A's questions

#### Scenario: Clearing it
- **WHEN** an editor chooses "No survey" for a report with three blocks
- **THEN** the report has no home survey and still has its three blocks

#### Scenario: A survey the member only views
- **WHEN** a member without the editor role on survey A posts A as the report's home survey
- **THEN** the home survey is unchanged

#### Scenario: Switches without a survey
- **WHEN** a report without a home survey is opened in the editor and its settings are saved
- **THEN** the two survey switches are not shown and their stored values are unchanged

#### Scenario: An adopted blank report is not drafted over
- **WHEN** a blank report becomes the only report of a published survey and the survey's Public results tab is opened
- **THEN** the report has no blocks it was not given by its author

### Requirement: Key numbers arrive filled and are picked, not typed as tokens
The system SHALL fill a Key numbers block added in the editor to a report with a home survey with
the numbers a drafted report opens with — people who opened, answered and finished the survey, and
the marks on its first map question when it has one — each following the answers. A block added to
a report without a home survey SHALL arrive empty for typed numbers. The editor SHALL offer the
survey's numbers with their current values in a menu, both to add a number and to change a number
that follows the answers, together with a number the author types; and SHALL NOT show token
syntax in the Key numbers block or its settings.

#### Scenario: A filled block on the first click
- **WHEN** an editor adds a Key numbers block to a report of a survey with a map question
- **THEN** the block holds four numbers that follow the answers and the page shows their values, with no notice that the block is left out

#### Scenario: A report without a survey
- **WHEN** an editor adds a Key numbers block to a report without a home survey
- **THEN** the block is empty and takes typed numbers

#### Scenario: The menu of survey numbers
- **WHEN** the editor of a report of a survey is opened
- **THEN** it offers the survey's numbers with their current values and a number to type, and the Key numbers settings name no token

#### Scenario: A number that follows the answers is not a text field
- **WHEN** a Key numbers block holds a number that follows the answers
- **THEN** the canvas marks it as live and shows its value, not its token

#### Scenario: A typed number
- **WHEN** an editor saves a row with a typed value and a label
- **THEN** the block holds it as typed

