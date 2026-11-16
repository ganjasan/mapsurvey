## ADDED Requirements

### Requirement: A report is a workspace object over Data datasets
The system SHALL keep a report as an object of a workspace with an ordered list of blocks, where a
block that shows data names a dataset of the Data module and, for a block about one question, that
question's code. A report SHALL own no answers, and its blocks MAY name datasets of several surveys
of the same workspace.

#### Scenario: Blocks over two surveys
- **WHEN** a report holds a chart block over survey A's responses and a map block over survey B's answers
- **THEN** the report's page shows both blocks, each with its own survey's aggregates

#### Scenario: A question replaced by publishing changes
- **WHEN** unpublished changes are published and the question rows of a survey are replaced
- **THEN** the report's blocks still show that question's answers across all versions

#### Scenario: A dataset that disappeared
- **WHEN** the question a block names no longer exists in any version of the survey
- **THEN** the block is left out of the page and the other blocks render

### Requirement: Existing public results pages are reports
The system SHALL turn every existing public results page into a report with the same address,
blocks in the same order with the same ids, visibility, publication state, live or frozen mode with
its snapshot, and K threshold, and SHALL keep no second page model.

#### Scenario: A published page after the migration
- **WHEN** a published page with a chart block and a map block is migrated
- **THEN** `/r/<its slug>/` returns the same blocks with the same numbers

#### Scenario: A frozen page after the migration
- **WHEN** a frozen page is migrated
- **THEN** the report is frozen at the same date and serves the same snapshot

#### Scenario: A comment thread on a block
- **WHEN** a block with an open comment thread is migrated
- **THEN** the thread is still anchored to that block

### Requirement: A survey opens its report
The system SHALL open a survey's report from the survey's Public results tab, creating an empty one
on first visit, and SHALL use that report for the thanks-page button, the Share page and the
dashboard's results pill.

#### Scenario: The tab of a migrated survey
- **WHEN** an editor opens the Public results tab of a survey that had a page
- **THEN** the configuration shows that page's blocks

### Requirement: Workspace-only visibility
The system SHALL offer a visibility under which a published report opens only for signed-in members
of its workspace, is never indexed and never listed.

#### Scenario: A member opens it
- **WHEN** a signed-in member of the workspace opens `/r/<slug>/` of a published workspace-only report
- **THEN** the report renders with `noindex`

#### Scenario: A stranger opens it
- **WHEN** a signed-in user who is not a member opens it
- **THEN** the system returns 404

#### Scenario: An anonymous visitor opens it
- **WHEN** an anonymous visitor opens it
- **THEN** the system sends them to the login page

### Requirement: The workspace lists its reports
The system SHALL list the reports of the active workspace that the member may see on a Reports page
reachable from the editor navigation, each with its state and a way to open its editor and its
public address.

#### Scenario: The list
- **WHEN** a member opens Reports in a workspace with a published and an unpublished report
- **THEN** both are listed with their state

#### Scenario: A survey the member cannot see
- **WHEN** an editor without a role on a survey opens Reports
- **THEN** that survey's report is not listed

### Requirement: A view shown by a report cannot be deleted
The system SHALL refuse to delete a view that a report block shows and SHALL say that a report uses it.

#### Scenario: Deleting a view in a block
- **WHEN** the owner deletes a view a report block shows
- **THEN** the view stays and the refusal names the use
