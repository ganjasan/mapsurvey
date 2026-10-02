## ADDED Requirements

### Requirement: One definition of an empty session
A session SHALL be empty when it has no `Answer` row with `parent_answer_id IS NULL`. Answers about
layer objects and answers a moderator hid SHALL count as answers. The Responses page, the session
issue computation and the data export SHALL decide emptiness through one shared helper, so they
never disagree about which sessions are empty.

#### Scenario: Object answer makes a session non-empty
- **WHEN** a session's only answer is a reaction to a layer object (`layer_object` set, no parent)
- **THEN** the session is not empty on the Responses page and is present in the export

#### Scenario: Hidden answer still counts
- **WHEN** a session's only answer was hidden by the creator's moderation
- **THEN** the session is not empty

#### Scenario: Geo sub-answer alone does not count
- **WHEN** a session has no top-level answer at all
- **THEN** the session is empty, and the `empty` issue and the export agree on it

### Requirement: Responses hides empty sessions by default
When `RESPONSES_V2` is on, the Responses page SHALL leave empty sessions out of the table, the
Overview (KPIs, feeds, trend) and the Responses tab badge unless the creator has chosen to show
them. Answer-based surfaces (Map, Charts, object statistics) are unaffected because empty sessions
hold no answers. The choice SHALL be remembered per browser and SHALL apply to every survey and
every version scope. Trash SHALL list deleted sessions whether or not they are empty. The legacy
dashboard (`RESPONSES_V2` off) SHALL keep listing every session.

#### Scenario: Default hides
- **WHEN** a survey has 5 non-deleted sessions of which 2 are empty and the creator opens Responses
  for the first time
- **THEN** the table lists 3 rows, the responses KPI and the tab badge read 3

#### Scenario: Choice survives navigation
- **WHEN** the creator shows empty sessions and then switches the version scope or reloads
- **THEN** empty sessions are still shown

#### Scenario: Trash ignores the choice
- **WHEN** an empty session is deleted and the creator opens the Trash view with empty sessions
  hidden
- **THEN** the deleted empty session is listed in Trash

### Requirement: The headline states both numbers and offers the toggle
The Overview KPI strip and the Responses table toolbar SHALL state, whenever the version scope
holds at least one empty session, the number of responses and the number of empty sessions,
e.g. "146 responses · 204 opened without answering", with a control that shows or hides the empty
sessions. When empty sessions are shown the line SHALL say so and the control SHALL hide them.
When the scope holds no empty session, no extra line or control SHALL render.

#### Scenario: Hidden count is visible
- **WHEN** the scope has 146 non-empty and 204 empty sessions and empty sessions are hidden
- **THEN** the KPI strip reads "146 responses" and "204 opened without answering" with a Show
  control

#### Scenario: Toggle shows them
- **WHEN** the creator activates Show
- **THEN** the page reloads with the 204 empty sessions listed in the table and counted in the KPIs,
  and the control now reads Hide

#### Scenario: No empty sessions
- **WHEN** every session in scope has an answer
- **THEN** the KPI strip and toolbar render no "opened without answering" line and no toggle

### Requirement: Sequence numbers count responses only
The per-survey sequence number (`#N`) SHALL be the rank by start time among non-empty, non-deleted
sessions of the version scope, so the newest response carries the headline count. Empty sessions,
when shown, SHALL render without a number, so showing or hiding them never renumbers responses.

#### Scenario: Numbers skip empty sessions
- **WHEN** sessions A (answered), B (empty), C (answered) started in that order
- **THEN** A is #1 and C is #2, with or without empty sessions shown, and B shows no number

### Requirement: Whitespace-only text is not an answer
The respondent section POST SHALL treat a value that is empty after stripping whitespace as blank
for every input type, and SHALL store text, text-line, datetime, number and range values stripped.
This SHALL apply to the main section fields and to answers about layer objects.

#### Scenario: Spaces do not create an answer
- **WHEN** a respondent submits a section whose only text field holds "   "
- **THEN** no `Answer` row is created and the session stays empty

#### Scenario: Spaces in a number field do not crash
- **WHEN** a respondent submits "  " in a number field
- **THEN** the section saves without an error and stores no answer for that question

#### Scenario: Surrounding spaces are trimmed
- **WHEN** a respondent submits "  bus stop  " in a text field
- **THEN** the stored answer text is "bus stop"
