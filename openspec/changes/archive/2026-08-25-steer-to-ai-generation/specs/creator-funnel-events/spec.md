# creator-funnel-events (delta)

## ADDED Requirements

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
