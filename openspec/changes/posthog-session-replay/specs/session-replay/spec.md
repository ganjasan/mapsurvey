## ADDED Requirements

### Requirement: Recording is off unless explicitly enabled

The system SHALL render a snippet that permits session recording only when a `POSTHOG_SESSION_REPLAY`
setting is enabled. When it is disabled or absent, the rendered snippet SHALL explicitly disable
session recording, so that no project-level setting can start a recording.

The setting SHALL default to disabled, so local development, the test suite, PR previews, forks and
self-hosted installs record nothing without a deliberate decision.

#### Scenario: Disabled by default
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured and `POSTHOG_SESSION_REPLAY` is unset
- **WHEN** a creator-facing page is rendered
- **THEN** the snippet's initialisation disables session recording

#### Scenario: Enabled by configuration
- **GIVEN** `POSTHOG_PROJECT_KEY` is configured and `POSTHOG_SESSION_REPLAY` is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** the snippet's initialisation does not disable session recording

#### Scenario: No key means no recording regardless
- **GIVEN** `POSTHOG_PROJECT_KEY` is empty and `POSTHOG_SESSION_REPLAY` is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** no PostHog snippet is rendered at all

### Requirement: Typed content is never recorded

When recording is enabled, the rendered snippet SHALL configure input masking so that the contents of
form fields are masked in the browser, before any recording payload is transmitted.

Where a recorded request URL would carry typed content in its query string, the snippet SHALL strip
the query string before the request is stored. The snippet SHALL NOT enable recording of request
bodies or headers.

#### Scenario: Input masking is present whenever recording is possible
- **GIVEN** recording is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** the snippet's session-recording configuration masks all inputs

#### Scenario: Interface text is not masked
- **GIVEN** recording is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** the configuration does not mask all text, so the product's own interface stays legible in
  playback

#### Scenario: Recorded request URLs carry no query string
- **GIVEN** recording is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** the configuration rewrites every recorded request to drop its query string

#### Scenario: Request bodies and headers are not recorded
- **GIVEN** recording is enabled
- **WHEN** a creator-facing page is rendered
- **THEN** nothing in the configuration enables body or header recording

### Requirement: Respondent surfaces cannot be recorded

The system SHALL NOT render a recording-capable snippet on any surface matching
`POSTHOG_EXCLUDED_PREFIXES`. Enabling recording SHALL NOT change which surfaces carry the snippet.

#### Scenario: Survey pages carry no snippet with recording enabled
- **GIVEN** recording is enabled and a project key is configured
- **WHEN** a respondent requests a page under `/surveys/`
- **THEN** the response contains no PostHog snippet and no session-recording configuration

#### Scenario: Public results pages carry no snippet with recording enabled
- **GIVEN** recording is enabled and a project key is configured
- **WHEN** a visitor requests a page under `/r/`
- **THEN** the response contains no PostHog snippet and no session-recording configuration

### Requirement: The trust page discloses recording

`/trust/` SHALL state that sessions in the editor are recorded, that typed content is masked, how
long recordings are retained, and that respondents are never recorded. The disclosure SHALL be
present whenever the capability is shipped, not added afterwards.

#### Scenario: Recording is disclosed
- **WHEN** a visitor reads `/trust/`
- **THEN** the page states that creator sessions in the editor may be recorded
- **AND** states that what creators type is masked
- **AND** states the retention period for recordings

#### Scenario: The respondent boundary is restated
- **WHEN** a visitor reads what `/trust/` says about recording
- **THEN** the page states that people answering surveys are never recorded
