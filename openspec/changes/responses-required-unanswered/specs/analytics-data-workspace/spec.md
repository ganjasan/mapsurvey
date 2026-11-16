## MODIFIED Requirements

### Requirement: Response table defaults serve reading, not administration
When `RESPONSES_V2` is on the response table SHALL default to: per-survey sequence number, start
time, duration, status chip, then answer columns; language and version columns SHALL be available
but hidden by default. Validation status SHALL render as a chip opening a control on demand, not
as an always-rendered per-row select. The Violations sidebar SHALL be replaced by toolbar filter
chips (all / complete / required unanswered / trash) with counts, as described in
`responses-required-unanswered`. Trash SHALL be a view chip, not an action-styled button. Row
activation SHALL open the session detail surface.

#### Scenario: Default columns fit reading order
- **WHEN** the Responses pane renders with default settings
- **THEN** sequence, start time, duration and status precede answer columns, and language/version
  are hidden until enabled via the columns control

#### Scenario: Required-unanswered chip filters
- **WHEN** the creator activates the "required unanswered" chip
- **THEN** the table shows only sessions with missing required questions and the chip shows their
  count

## REMOVED Requirements

### Requirement: Violation filtering keeps per-type selection
**Reason**: The violation types it listed (duplicate, incomplete, fast, missing required,
outliers, short text, out of range) are removed (#691); most of their marks were wrong and
creators deleted real answers because of them.
**Migration**: The single "Required unanswered" filter (`required=missing`) replaces the menu; an
old `issues=` link is ignored and shows all rows.

## ADDED Requirements

### Requirement: Bulk delete states how many responses it will delete
Bulk "Move to trash" and bulk "Delete permanently" SHALL ask for confirmation in the app's
in-page delete dialog (title, what is lost, Cancel and a danger button), never `window.confirm`,
and the dialog SHALL state how many responses the action will affect, whatever selected them.

#### Scenario: Trash 37 selected rows
- **WHEN** the creator selects 37 rows and presses Move to trash
- **THEN** a dialog reads "Move 37 responses to trash?" and nothing is trashed until the danger
  button is pressed

#### Scenario: Permanent delete warns it cannot be undone
- **WHEN** the creator selects 5 trashed rows and presses Delete permanently
- **THEN** the dialog names 5 responses and says this cannot be undone
