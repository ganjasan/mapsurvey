# operator-entry Specification

## Purpose
The operator entry form (change operator-entry, #355, epic #350): a workspace member enters a
survey's answers on someone's behalf — a paper sheet, an assisted interview, a field
observation — producing an ordinary session that every read surface understands but no funnel
counts.
## Requirements
### Requirement: Operator entry is opened from Responses by editors of a Pro workspace
The Responses page SHALL offer *Enter a response* to members with the `editor` role or above on
the survey. The entry header and every entry URL SHALL be gated by the Pro feature `operator_entry`
on the organisation that owns the survey, checked per request. Without the feature the control
SHALL render locked with a link to the billing page and the entry URLs SHALL answer the standard
feature refusal; sessions entered while the feature was held SHALL remain.

#### Scenario: Editor of a Pro workspace opens the form
- **WHEN** an `editor` of a Pro organisation clicks *Enter a response* on Responses
- **THEN** the entry header renders

#### Scenario: Viewer cannot enter
- **WHEN** a `viewer` requests the entry header URL
- **THEN** the response is 403

#### Scenario: Free workspace sees the lock
- **WHEN** an `editor` of a Free organisation opens Responses
- **THEN** *Enter a response* is rendered locked with the upgrade link
- **AND** a request to the entry header URL answers the `require_feature` refusal

#### Scenario: Lapsed subscription keeps entered sessions
- **GIVEN** three sessions were entered while the organisation was Pro
- **WHEN** the entitlement lapses
- **THEN** the three sessions are still listed on Responses and the entry URLs refuse new entries

#### Scenario: Closed survey accepts entries
- **WHEN** an editor opens the entry header of a `closed` survey
- **THEN** the header renders — a closed survey is where sheets get entered

### Requirement: The entry header fixes source, version and language
The entry header SHALL ask for the **source** (`paper`, `assisted`, `field`, `other`; required),
the **survey version** the answers belong to (every version of the family, the live one selected
by default) and the **language** (the survey's languages, the primary selected by default).
Submitting it SHALL create a `SurveySession` on the chosen version's header with `source`,
`language`, `entered_by` = the signed-in user and `opened_by_kind` derived as for any signed-in
opener, then redirect to the first visible section of the entry flow.

#### Scenario: Sheet from an archived version
- **GIVEN** a survey with versions v1 (archived) and v2 (live)
- **WHEN** the operator submits the header with version v1 and source `paper`
- **THEN** the created session's `survey` is the v1 header, `source='paper'`, `entered_by` is the operator

#### Scenario: Source is required
- **WHEN** the header is submitted without a source
- **THEN** the header re-renders with a field error and no session is created

#### Scenario: Language on a multilingual survey
- **WHEN** the operator chooses `pl` on a survey offering `en` and `pl`
- **THEN** the session's `language` is `pl` and the entry sections render in Polish

### Requirement: The entry flow walks the survey like a respondent would, keyed by URL
Entry sections SHALL be served at `/editor/surveys/<uuid>/responses/enter/<session_id>/<section>/`
and SHALL render the survey's sections with the same partials and scripts the respondent page uses,
in entry mode: no language picker, no abuse footer, no embed carrier, no product analytics. The
view SHALL honour a session only when it belongs to the survey's version family, has
`source != online`, and the caller holds the `editor` role; the respondent browser-session cookie
SHALL be neither read nor written. Section navigation, the visibility chain and answer storage SHALL
be the respondent page's (the same save function), evaluated for the `operator` surface.

#### Scenario: Someone else's session id
- **WHEN** an editor requests an entry URL whose session belongs to another survey
- **THEN** the response is 404

#### Scenario: A respondent session cannot be entered
- **WHEN** an editor requests an entry URL with the id of a session whose `source` is `online`
- **THEN** the response is 404

#### Scenario: The respondent cookie is untouched
- **GIVEN** the operator's browser carries a respondent session cookie for the same survey
- **WHEN** they enter a sheet
- **THEN** the cookie still names the respondent session and the entered answers are on the operator session

#### Scenario: Answers are stored like a respondent's
- **WHEN** the operator submits a section with a choice, a text and a point answer
- **THEN** the session has one `Answer` row per question with the same columns a respondent's would have

#### Scenario: Visibility applies
- **GIVEN** a section shown only when question Q1 is "Yes"
- **WHEN** the operator enters "No" for Q1 and continues
- **THEN** the hidden section is skipped and nothing is stored for it

### Requirement: Respondent-facing required fields never block an operator
In entry mode a question whose effective audience includes respondents SHALL be built without
`required`, whatever `Question.required` says; a question whose effective audience is `operators`
SHALL keep its own `required`. Structural validation — choice codes, geometry clamps, hidden-answer
purge — SHALL be unchanged.

#### Scenario: Blank on paper stays blank
- **GIVEN** a required choice question shown to respondents
- **WHEN** the operator submits the section without answering it
- **THEN** the section is accepted and no `Answer` row exists for that question

#### Scenario: Operator's own field is required
- **GIVEN** an `operators`-only text question "Sheet number" marked required
- **WHEN** the operator submits the section without it
- **THEN** the field is required in the rendered form (`required` attribute present)

### Requirement: Finishing stores a completed session and offers the next sheet
Submitting the last visible section SHALL set `end_datetime` on the session and render a "Saved"
page with *Next sheet* — which opens the header prefilled with the previous source, version and
language — and *Back to Responses*. Cancelling from the header SHALL create nothing; abandoning a
started entry SHALL leave an empty session that Responses treats like any other empty session.

#### Scenario: Finish completes the session
- **WHEN** the operator submits the last visible section
- **THEN** the session's `end_datetime` is set and the Saved page renders

#### Scenario: Next sheet keeps the header
- **GIVEN** the previous entry used source `paper`, version v1, language `pl`
- **WHEN** the operator clicks *Next sheet*
- **THEN** the header renders with those three values preselected

#### Scenario: Abandoned entry
- **WHEN** the operator submits the header and closes the tab
- **THEN** one empty session exists, hidden by the Responses default and shown by the empty-sessions toggle

### Requirement: Operator sessions have no respondent side effects
A session with `source != online` SHALL write no `SurveyEvent` rows, SHALL never emit
`survey_first_response` or any creator milestone, SHALL never be recorded as a demo open, SHALL
not be materialised into question-sourced reference layers, and SHALL not be counted by the Perf
pane or any funnel.

#### Scenario: No events
- **WHEN** an operator enters a complete sheet
- **THEN** `SurveyEvent.objects.filter(session=...)` is empty

#### Scenario: No first-response milestone
- **GIVEN** a survey with no sessions
- **WHEN** an operator enters a sheet and, later, an anonymous respondent opens the survey
- **THEN** exactly one `survey_first_response` is emitted, at the respondent's session

#### Scenario: Shared map ignores the sheet
- **GIVEN** a reference layer sourced from the geo question Q3
- **WHEN** an operator enters a point for Q3
- **THEN** the layer has no object for that session

### Requirement: Responses, the drawer and exports show the source
The Responses table SHALL carry a *Source* column (after Status) with a values filter
(`online`, `paper`, `assisted`, `field`, `other`); the detail drawer SHALL state the source and
the operator's name; every session-level export (`sessions` table, responses ZIP file) SHALL
include `source` and `entered_by` (username).
Overview counts, question statistics, public results and the data export SHALL include operator
sessions as answers.

#### Scenario: Filter paper only
- **WHEN** the table is requested with `cf_source=v:paper`
- **THEN** only sessions with `source='paper'` are listed

#### Scenario: Drawer names the operator
- **WHEN** the drawer opens on an operator session
- **THEN** it shows the source label and the operator's username

#### Scenario: Export columns
- **WHEN** the workbook export runs
- **THEN** the `sessions` sheet has `source` and `entered_by` columns and an online session reads `online` and blank

#### Scenario: Counted as answers
- **GIVEN** 4 online sessions and 2 paper sessions with answers
- **WHEN** the Overview renders
- **THEN** the response count is 6

