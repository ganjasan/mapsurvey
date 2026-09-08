# acquisition-metrics-sync Specification

## Purpose
Record demo-survey opens with their authentication state for the staff funnel dashboard. The
provider sync this capability used to describe (Search Console and Plausible into local daily
records) was retired by `acquisition-instrumentation`: search impressions, landing visits and
channel mix are read on the PostHog AARRR dashboard from PostHog's own warehouse sources.
## Requirements
### Requirement: Demo opens are recorded with their authentication state

The system SHALL resolve the demo survey from the configured demo survey URL and, for every
respondent session started on that survey, record a demo-open entry carrying the session, the
authenticated user when one is present, and the time. Sessions on any other survey SHALL NOT
produce such an entry, and respondent identity SHALL NOT be added to the shared session table.

#### Scenario: An anonymous visitor opens the demo

- **WHEN** an unauthenticated visitor starts a session on the demo survey
- **THEN** a demo-open entry is recorded with no associated user

#### Scenario: A signed-in user opens the demo

- **WHEN** an authenticated user starts a session on the demo survey
- **THEN** a demo-open entry is recorded referencing that user

#### Scenario: Other surveys are untouched

- **WHEN** a session is started on any survey other than the demo survey
- **THEN** no demo-open entry is recorded and the session stores no respondent identity

#### Scenario: The demo survey cannot be resolved

- **WHEN** the demo survey URL is unset, malformed, or points at a survey that no longer exists
- **THEN** session creation proceeds normally, no demo-open entry is recorded, and no error is
  raised to the respondent

