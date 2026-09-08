# creator-distribution-events Specification

## Purpose
PostHog creator events for the step between "published" and "answered": sharing a survey (link,
QR, embed) and returning to its data (responses page, export). Creator-only, `survey_id` plus a
surface, never a slug, URL or anything about a respondent.
## Requirements
### Requirement: Creator sharing actions are captured
The system SHALL capture PostHog events when a creator copies the survey link
(`share_link_copied`), shows the QR code (`qr_shown`) or copies the embed snippet
(`embed_copied`). Each event SHALL carry `survey_id` and `surface` (the editor pane the action was
taken from) and nothing else. Browser captures SHALL be guarded by the presence of the PostHog
client and SHALL degrade to silence when the key is unset or the client is blocked.

#### Scenario: Link copied
- **WHEN** a creator clicks the copy-link control in the editor
- **THEN** one `share_link_copied` event with `survey_id` and `surface` is captured

#### Scenario: Client blocked
- **WHEN** the PostHog client is absent and the creator copies the link
- **THEN** the copy works and no capture is attempted

#### Scenario: No respondent-facing URL in the payload
- **WHEN** any sharing event is captured
- **THEN** its properties contain no survey slug, public URL or QR payload

### Requirement: Creator return-to-data actions are captured server-side
The system SHALL emit `responses_viewed` when a creator loads a survey's responses page and
`data_exported` (with `format`) when a creator downloads survey data or exports a survey
definition. Both SHALL go through `product_events.emit`, be attributed to the acting creator,
carry `survey_id`, and never block or alter the response.

#### Scenario: Responses page opened
- **WHEN** a creator opens the responses view of a survey
- **THEN** one `responses_viewed` event with `survey_id` is emitted for that request

#### Scenario: Data downloaded
- **WHEN** a creator downloads the responses ZIP
- **THEN** one `data_exported` event with `survey_id` and `format='zip'` is emitted and the download
  is served unchanged

#### Scenario: PostHog unconfigured
- **WHEN** PostHog is disabled
- **THEN** the views behave exactly as before and nothing is sent

