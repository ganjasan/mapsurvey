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

### Requirement: Survey creation records its surface and map source
The `survey_created` event SHALL carry `surface` — `start_blank` for the one-request
blank endpoint, `create_page` for both actions of `/editor/surveys/new/` — and
`map_source` as defined in `map-start-position` (`browser`, `org_survey`, `country`,
`world`, `creator`, `brief`). Neither property SHALL carry coordinates, a place name or
any creator-written text; `creation_method` is unchanged.

#### Scenario: Blank endpoint
- **WHEN** a survey is created through `/editor/surveys/new/blank/` with no browser position in an organization without positioned surveys and no resolvable country
- **THEN** `survey_created` carries `creation_method='manual'`, `surface='start_blank'`, `map_source='world'`

#### Scenario: Create page manual action
- **WHEN** a survey is created with the create page's manual action and an untouched map
- **THEN** `survey_created` carries `surface='create_page'` and the `map_source` posted by the page

#### Scenario: No coordinates in the payload
- **WHEN** any `survey_created` event is emitted
- **THEN** its properties contain no latitude, longitude, place name or country code

### Requirement: Agent access interest event
The system SHALL emit `agent_access_requested` once per creator, when
`CreatorPreferences.agent_access_requested_at` is first set from the agent access page,
attributed to the creator and carrying no further properties.

#### Scenario: First request emits
- **WHEN** a creator posts "Tell me when it's ready" for the first time
- **THEN** one `agent_access_requested` event is emitted for that creator

#### Scenario: Repeat request is silent
- **WHEN** the same creator posts it again
- **THEN** no event is emitted

### Requirement: Comment thread activity is emitted as creator events
The system SHALL emit `comment_thread_opened`, `comment_reply_posted` and
`comment_thread_resolved` through `product_events.emit` when a member opens a thread, posts a
reply or resolves a thread. Properties SHALL be limited to `survey_id`, `organization_id` and
`anchor_kind`; the comment body, mentions and attachment names SHALL never be attached.
Without a PostHog client the emission SHALL be a silent no-op.

#### Scenario: Reply emits one event
- **WHEN** a member posts a reply in a thread on a question
- **THEN** exactly one `comment_reply_posted` is captured with `distinct_id` = the member's user id and `anchor_kind` = `question`, and the payload contains no body text

#### Scenario: No PostHog client, no error
- **WHEN** `POSTHOG_PROJECT_KEY` is unset and a thread is resolved
- **THEN** the request succeeds and nothing is captured

