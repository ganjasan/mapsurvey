## ADDED Requirements

### Requirement: Local daily store for external acquisition metrics

The system SHALL persist acquisition metrics fetched from external providers as daily records keyed
by `(source, date, segment)`, where `source` identifies the provider (`gsc`, `plausible`) and
`segment` identifies the slice within that provider. Metrics that do not apply to a source SHALL be
stored as NULL rather than zero. No component outside the sync command SHALL call an external
analytics API.

#### Scenario: A day is stored once per source and segment

- **WHEN** metrics for a given source, date, and segment are written
- **THEN** exactly one record exists for that combination, and writing the same combination again
  updates it in place instead of creating a duplicate

#### Scenario: Inapplicable metrics stay unset

- **WHEN** a Plausible record is stored
- **THEN** its impressions and search-position fields are NULL, and are distinguishable from a
  genuine measured zero

#### Scenario: The dashboard reads only local records

- **WHEN** the funnel dashboard is rendered
- **THEN** no request is made to Google Search Console or Plausible during the response

### Requirement: Search Console ingestion split by page group

The system SHALL fetch impressions, clicks, click-through rate, and average position from Google
Search Console for the configured property, storing both a whole-property record and a record
restricted to marketing pages. Survey pages under `/surveys/` SHALL be excluded from the marketing
page group. Both records SHALL be fetched under the same provider aggregation mode, so that the two
segments remain comparable and subtractable.

#### Scenario: Both page groups are recorded

- **WHEN** a Search Console sync completes for a date
- **THEN** that date has a whole-property record and a marketing-pages record, and the marketing
  record's impressions are less than or equal to the whole-property record's

#### Scenario: Survey traffic is excluded from the marketing group

- **WHEN** the marketing page group is computed for a date on which survey pages received
  impressions
- **THEN** those impressions are absent from the marketing record

#### Scenario: Both segments are queried page-level

- **WHEN** the whole-property record is fetched
- **THEN** the request carries a page filter matching every URL, so the provider aggregates by page
  exactly as it does for the filtered marketing request, and the whole-property total is never
  smaller than the marketing total for the same date

### Requirement: Plausible ingestion of landing traffic and channels

The system SHALL fetch visitor and pageview counts from the Plausible Stats API for the configured
site, storing a whole-site record, a landing-page record, and one record per referrer channel.

#### Scenario: Channel breakdown is stored per channel

- **WHEN** a Plausible sync completes for a date on which visitors arrived from several referrer
  channels
- **THEN** one record exists per channel for that date, each identifiable by its channel name

#### Scenario: Landing traffic is recorded separately from whole-site traffic

- **WHEN** a Plausible sync completes for a date
- **THEN** that date has both a whole-site record and a landing-page record

### Requirement: Idempotent, windowed synchronisation command

The system SHALL provide a management command that synchronises a trailing window of days,
defaulting to the last 7, and accepting an explicit window length and an optional single-source
restriction. Re-running the command for an already-synchronised window SHALL overwrite those days
with the freshly fetched values and SHALL NOT create duplicate records.

#### Scenario: Re-running the command overwrites rather than duplicates

- **WHEN** the command is run twice for the same window
- **THEN** the record count is unchanged after the second run and the stored values reflect the
  second run's response

#### Scenario: Revised provider data replaces earlier values

- **WHEN** a provider returns a different value for a date already stored
- **THEN** the stored record is updated to the newly returned value

#### Scenario: A single source can be synchronised alone

- **WHEN** the command is run restricted to one source
- **THEN** only that source's records are written and the other source's records are left untouched

#### Scenario: A wide window backfills history

- **WHEN** the command is run with a window longer than the existing history
- **THEN** records are created for every day the provider returns data for

### Requirement: Per-source sync state and failure isolation

The system SHALL record, per source, the time of the last attempt, the time of the last success,
and the message of the last failure. A failure of one source SHALL NOT prevent the other source
from being synchronised, and SHALL NOT delete or zero previously stored records.

#### Scenario: One provider failing leaves the other unaffected

- **WHEN** a sync runs while one provider returns an error and the other succeeds
- **THEN** the succeeding source's records are written and its state records a success, while the
  failing source's state records the error and its previously stored records remain unchanged

#### Scenario: A recovered provider clears the failure state

- **WHEN** a source that previously failed synchronises successfully
- **THEN** its state shows the new success time and no longer reports an outstanding error

#### Scenario: The command reports failure to its caller

- **WHEN** every requested source fails
- **THEN** the command exits with a non-zero status so the scheduled job is visibly failed

### Requirement: Missing credentials are a reported state, not an error

The system SHALL treat an absent or unusable provider credential as a distinct "not configured"
state: the sync SHALL skip that source without raising, and the state record SHALL make the reason
retrievable. Credentials SHALL be read from the environment and SHALL NOT be stored in the
repository.

#### Scenario: Sync runs with no credentials configured

- **WHEN** the command runs while neither provider is configured
- **THEN** it completes without raising, writes no metric records, and both sources report the
  not-configured reason

#### Scenario: Not configured is distinguishable from failing

- **WHEN** a consumer inspects a source's state
- **THEN** it can tell apart a source that was never configured, a source that is configured and
  succeeding, and a source that is configured but failing

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
