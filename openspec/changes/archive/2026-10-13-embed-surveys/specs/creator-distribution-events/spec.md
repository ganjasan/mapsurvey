## MODIFIED Requirements

### Requirement: Creator sharing actions are captured
The system SHALL capture PostHog events when a creator copies the survey link
(`share_link_copied`), shows the QR code (`qr_shown`) or copies the embed snippet
(`embed_copied`). Each event SHALL carry `survey_id` and `surface` (the editor pane the action was
taken from) and nothing else. Browser captures SHALL be guarded by the presence of the PostHog
client and SHALL degrade to silence when the key is unset or the client is blocked.

#### Scenario: Link copied
- **WHEN** a creator clicks the copy-link control in the editor
- **THEN** one `share_link_copied` event with `survey_id` and `surface` is captured

#### Scenario: Embed snippet copied
- **WHEN** a creator clicks the copy control of the Embed section on the Share page
- **THEN** one `embed_copied` event with `survey_id` and `surface: "share_page"` is captured

#### Scenario: Client blocked
- **WHEN** the PostHog client is absent and the creator copies the link
- **THEN** the copy works and no capture is attempted

#### Scenario: No respondent-facing URL in the payload
- **WHEN** any sharing event is captured
- **THEN** its properties contain no survey slug, public URL, snippet or QR payload
