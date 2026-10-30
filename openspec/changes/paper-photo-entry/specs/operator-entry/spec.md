# operator-entry — delta for paper-photo-entry

## MODIFIED Requirements

### Requirement: The entry header fixes source, version and language
The entry header SHALL ask for the **source** (`paper`, `assisted`, `field`, `other`; required),
the **survey version** the answers belong to (every version of the family, the live one selected
by default) and the **language** (the survey's languages, the primary selected by default).
Submitting it SHALL create a `SurveySession` on the chosen version's header with `source`,
`language`, `entered_by` = the signed-in user and `opened_by_kind` derived as for any signed-in
opener, then redirect to the first visible section of the entry flow. The header SHALL link to
*From photos* (the paper batches of this survey, spec paper-photo-entry), and a sheet's review SHALL
skip the header: the printed form's version and language and the source `paper` are the session's.

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

#### Scenario: Sheet review skips the header
- **WHEN** a sheet of a form printed from version v1 in `pl` is opened for review
- **THEN** the session is created on v1 in `pl` with `source='paper'` without rendering the header

### Requirement: The entry flow walks the survey like a respondent would, keyed by URL
Entry sections SHALL be served at `/editor/surveys/<uuid>/responses/enter/<session_id>/<section>/`
and SHALL render the survey's sections with the same partials and scripts the respondent page uses,
in entry mode: no language picker, no abuse footer, no embed carrier, no product analytics. The
view SHALL honour a session only when it belongs to the survey's version family, has
`source != online`, and the caller holds the `editor` role; the respondent browser-session cookie
SHALL be neither read nor written. Section navigation, the visibility chain and answer storage SHALL
be the respondent page's (the same save function), evaluated for the `operator` surface. When the
session has a `paper_sheet`, the section SHALL be prefilled from the sheet's extraction for every
question without an `Answer` row and rendered with the page pane (spec paper-photo-entry); a
session without a sheet SHALL render exactly as before.

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

#### Scenario: Session without a sheet is unchanged
- **WHEN** a typed-in session's section renders
- **THEN** no page pane and no prefill data are in the response

### Requirement: Finishing stores a completed session and offers the next sheet
Submitting the last visible section SHALL set `end_datetime` on the session and render a "Saved"
page with *Next sheet* — which opens the header prefilled with the previous source, version and
language — and *Back to Responses*. Cancelling from the header SHALL create nothing; abandoning a
started entry SHALL leave an empty session that Responses treats like any other empty session.
For a session with a `paper_sheet`, finishing SHALL additionally mark the sheet `entered` and
*Next sheet* SHALL open the batch's next sheet to review, or the batch list when none remains.

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

#### Scenario: Next sheet of a batch
- **GIVEN** a sheet session whose batch has another sheet in `review`
- **WHEN** the operator clicks *Next sheet* on the Saved page
- **THEN** that sheet's review opens, not the header

### Requirement: Responses, the drawer and exports show the source
The Responses table SHALL carry a *Source* column (after Status) with a values filter
(`online`, `paper`, `assisted`, `field`, `other`); the detail drawer SHALL state the source and
the operator's name and, for a session with a `paper_sheet`, the sheet and batch; every
session-level export (`sessions` table, responses ZIP file) SHALL include `source`, `entered_by`
(username), `paper_batch` and `paper_sheet` (sequence numbers, blank otherwise).
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
- **THEN** the `sessions` sheet has `source`, `entered_by`, `paper_batch` and `paper_sheet` columns and an online session reads `online` and blanks

#### Scenario: Counted as answers
- **GIVEN** 4 online sessions and 2 paper sessions with answers
- **WHEN** the Overview renders
- **THEN** the response count is 6
