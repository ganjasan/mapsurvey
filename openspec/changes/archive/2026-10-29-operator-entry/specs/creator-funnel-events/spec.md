# creator-funnel-events — delta for operator-entry

## MODIFIED Requirements

### Requirement: Survey sessions record the opener's relation to the survey
Each `SurveySession` SHALL record at creation whether it was opened by the survey's owner
(`owner`), by a collaborator (`collaborator`), by the editor preview (`preview`), or by anyone else
(`external`). The value SHALL be derived from the authenticated user and the survey's ownership
and collaborator rows only; nothing about an anonymous respondent SHALL be inspected or stored for
this purpose. Beside it each session SHALL record its `source`: `online` for every session the
respondent link creates, or the operator entry form's value (`paper`, `assisted`, `field`,
`other`) together with `entered_by`, the operator. `source` SHALL be set by the surface that
creates the session and never derived from the user.

#### Scenario: Owner opens their own survey
- **WHEN** the survey's creator, signed in, opens the survey's public URL
- **THEN** the created session has kind `owner` and source `online`

#### Scenario: Collaborator opens the survey
- **WHEN** a signed-in user linked to the survey by a `SurveyCollaborator` row opens it
- **THEN** the created session has kind `collaborator`

#### Scenario: Anonymous respondent
- **WHEN** an unauthenticated visitor opens the survey
- **THEN** the created session has kind `external` and source `online`

#### Scenario: Editor preview
- **WHEN** a session is created by the editor's live preview
- **THEN** the created session has kind `preview`

#### Scenario: Operator entry
- **WHEN** an owner enters a paper sheet through the entry form
- **THEN** the created session has kind `owner`, source `paper` and `entered_by` set to them

#### Scenario: Existing rows
- **WHEN** the columns are added
- **THEN** existing sessions default to `external` and `online` and no history is rewritten

### Requirement: First response means an external respondent
`survey_first_response` SHALL be emitted only for the first non-deleted session of kind `external`
and source `online` on a survey, and SHALL carry `respondent_kind='external'`. Sessions of kind
`owner`, `collaborator` or `preview`, and sessions of any other source, SHALL never emit it and
SHALL NOT suppress a later external online one.

#### Scenario: Author tests before anyone answers
- **WHEN** the owner opens the published survey and, an hour later, an anonymous respondent opens it
- **THEN** exactly one `survey_first_response` is emitted, at the respondent's session, with
  `respondent_kind='external'`

#### Scenario: Second external session
- **WHEN** a second anonymous respondent opens a survey that already has an external session
- **THEN** no event is emitted

#### Scenario: Entered sheets do not count
- **WHEN** ten paper sheets are entered and then an anonymous respondent opens the survey
- **THEN** exactly one `survey_first_response` is emitted, at the respondent's session

#### Scenario: Attribution and payload unchanged
- **WHEN** the event is emitted
- **THEN** it is attributed to the survey owner's distinct id and carries only `survey_id`,
  `creation_method`, `respondent_kind` and `timestamp_source`
