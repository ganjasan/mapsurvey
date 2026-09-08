## ADDED Requirements

### Requirement: Survey sessions record the opener's relation to the survey
Each `SurveySession` SHALL record at creation whether it was opened by the survey's owner
(`owner`), by a collaborator (`collaborator`), by the editor preview (`preview`), or by anyone else
(`external`). The value SHALL be derived from the authenticated user and the survey's ownership
and collaborator rows only; nothing about an anonymous respondent SHALL be inspected or stored for
this purpose.

#### Scenario: Owner opens their own survey
- **WHEN** the survey's creator, signed in, opens the survey's public URL
- **THEN** the created session has kind `owner`

#### Scenario: Collaborator opens the survey
- **WHEN** a signed-in user linked to the survey by a `SurveyCollaborator` row opens it
- **THEN** the created session has kind `collaborator`

#### Scenario: Anonymous respondent
- **WHEN** an unauthenticated visitor opens the survey
- **THEN** the created session has kind `external`

#### Scenario: Editor preview
- **WHEN** a session is created by the editor's live preview
- **THEN** the created session has kind `preview`

#### Scenario: Existing rows
- **WHEN** the column is added
- **THEN** existing sessions default to `external` and no history is rewritten

### Requirement: First response means an external respondent
`survey_first_response` SHALL be emitted only for the first non-deleted session of kind `external`
on a survey, and SHALL carry `respondent_kind='external'`. Sessions of kind `owner`,
`collaborator` or `preview` SHALL never emit it and SHALL NOT suppress a later external one.

#### Scenario: Author tests before anyone answers
- **WHEN** the owner opens the published survey and, an hour later, an anonymous respondent opens it
- **THEN** exactly one `survey_first_response` is emitted, at the respondent's session, with
  `respondent_kind='external'`

#### Scenario: Second external session
- **WHEN** a second anonymous respondent opens a survey that already has an external session
- **THEN** no event is emitted

#### Scenario: Attribution and payload unchanged
- **WHEN** the event is emitted
- **THEN** it is attributed to the survey owner's distinct id and carries only `survey_id`,
  `creation_method`, `respondent_kind` and `timestamp_source`
