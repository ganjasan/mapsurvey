## MODIFIED Requirements

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

## ADDED Requirements

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
