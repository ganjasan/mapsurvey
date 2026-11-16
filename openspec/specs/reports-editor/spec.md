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
The system SHALL let an editor delete a report after a page that says what goes with it, and SHALL
leave the survey's answers untouched.

#### Scenario: Deleting an imported report
- **WHEN** an editor confirms deleting a report
- **THEN** the report and its blocks are gone and the list no longer shows it

