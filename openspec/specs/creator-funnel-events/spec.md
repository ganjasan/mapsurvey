## Purpose

PostHog funnel events for the creator journey (registration -> survey creation ->
publication). Introduced by the still-active `ai-funnel-events` change; this file
currently holds the requirements that have already shipped and been archived.
## Requirements
### Requirement: Empty-path intercept events
The create page SHALL capture a client-side PostHog event `ai_empty_intercept` for each
intercept interaction, with properties `outcome` (`shown`, `accepted`, or `declined`)
and `surface` (`desktop` or `wizard`). Capture SHALL be guarded by the presence of the
PostHog client (`window.posthog`), degrading to silence when the project key is unset or
the client is blocked. The event SHALL NOT carry the brief's content or any other
creator-written text. Downstream conversion SHALL be read from the existing
`ai_draft_requested` and `survey_created` (`creation_method`) events, which this
requirement does not alter.

#### Scenario: Shown is captured once
- **WHEN** the intercept prompt is rendered for a creator on the desktop layout
- **THEN** one `ai_empty_intercept` event with `outcome='shown'` and `surface='desktop'` is captured

#### Scenario: Decline is captured
- **WHEN** the creator clicks "Create empty anyway"
- **THEN** one `ai_empty_intercept` event with `outcome='declined'` is captured before the empty submission proceeds

#### Scenario: Accept is captured
- **WHEN** the creator clicks "Generate draft" in the prompt
- **THEN** one `ai_empty_intercept` event with `outcome='accepted'` is captured and the generation flow starts

#### Scenario: No PostHog client, no error
- **WHEN** `POSTHOG_PROJECT_KEY` is empty or the client is blocked and the intercept fires
- **THEN** the interaction works normally and no capture is attempted

#### Scenario: Brief content never attached
- **WHEN** any `ai_empty_intercept` event is captured
- **THEN** its properties contain only `outcome` and `surface` — never the goal, audience, or map-target text

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

### Requirement: Activation is emitted on the direct-activation path
The system SHALL send `user_activated` after a successful activation on the confirmation page
(`DirectActivationView`), so that `creator_activated_account` is emitted with
`timestamp_source='live'`. A replayed key that hits the already-activated branch SHALL NOT emit.

#### Scenario: Confirmation POST emits exactly one activation event
- **WHEN** an inactive creator posts a valid activation key to the confirmation page
- **THEN** exactly one `creator_activated_account` is emitted for that creator, the account is
  active and the user is signed in

#### Scenario: Replayed key emits nothing
- **WHEN** the same key is posted again after activation
- **THEN** no activation event is emitted

