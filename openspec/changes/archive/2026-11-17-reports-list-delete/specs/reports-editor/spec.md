## MODIFIED Requirements

### Requirement: A report can be deleted
The system SHALL let an editor delete a report after a page that says what goes with it, and SHALL
leave the survey's answers untouched. The Delete action SHALL be offered on the report's row in the
Reports list and in the report's settings in the editor, for every report the member may edit,
whether or not the report has a home survey. It SHALL NOT be offered to a member who may not edit
the report. When the report is the one its survey's Public results tab opens, the page SHALL say
that the tab will open the survey's next report or start an empty one.

#### Scenario: Deleting an imported report
- **WHEN** an editor confirms deleting a report
- **THEN** the report and its blocks are gone and the list no longer shows it

#### Scenario: Delete in the list
- **WHEN** an editor opens the Reports list
- **THEN** every report they may edit has a Delete action that opens the page saying what goes

#### Scenario: A member who may not edit
- **WHEN** a viewer of the workspace opens the Reports list
- **THEN** no row offers Delete

#### Scenario: A report made from a survey
- **WHEN** an editor opens the settings of a report whose home is a survey
- **THEN** "Delete report…" is offered, and the delete page says what the survey's Public results tab will open afterwards

## ADDED Requirements

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
