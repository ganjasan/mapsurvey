# responses-overview — delta for layers-by-question

## ADDED Requirements

### Requirement: The response table reads the same whichever version header opens it
The response table SHALL key its question columns on the lineage representative of each
question (the canonical version's question, or the newest archived one), so that a table
opened from a draft copy, an archived version or the canonical survey shows the same
columns with the same cells for the same scope.

#### Scenario: Table opened from a draft copy
- **WHEN** a creator opens Responses on the draft copy of a published survey with answers
- **THEN** each answer appears in its question's column, exactly as on the published survey's Responses tab

### Requirement: Objects-on-the-map questions have no response-table column
The response table SHALL NOT show a column for a `layer_objects` question: its answers are
per object on its sub-questions (shown in the per-object table and the export's objects
sheet), and a display-only one collects nothing.

#### Scenario: Layer question in a section
- **WHEN** a section has a text question and an Objects question bound to a layer
- **THEN** the response table has a column for the text question only

### Requirement: Session timing lives on the session row
`SurveySession.last_activity_at` SHALL be written on every section submit and on the
page-leave beacon; `SurveySession.end_datetime` SHALL be set when the respondent reaches the
thanks page (first completion wins). The response table's Duration SHALL read
`end_datetime − start_datetime` for completed sessions and `last_activity_at −
start_datetime`, marked with a trailing "+", for sessions that left; it SHALL NOT depend on
the event log. Both timestamps SHALL ride the responses ZIP export and import. Existing rows
are backfilled once from the event log where one exists.

#### Scenario: Completed session
- **WHEN** a respondent submits the last section and lands on the thanks page
- **THEN** the session has `end_datetime`, and Duration shows the elapsed time without a "+"

#### Scenario: Abandoned session
- **WHEN** a respondent submits one section and closes the tab (page-leave beacon)
- **THEN** `last_activity_at` is set, `end_datetime` is not, and Duration shows the elapsed time with a "+"

#### Scenario: Imported responses
- **WHEN** responses are imported from a ZIP written after this change
- **THEN** the imported sessions keep their timing and show a Duration
