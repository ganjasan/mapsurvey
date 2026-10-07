## ADDED Requirements

### Requirement: Trends section of metric tiles
The dashboard SHALL open with a Trends section that renders every series of the metric registry
as a chart tile: the event series (`regs`, `activations`, `surveys_created`, `surveys_published`,
`first_responses`, `responses`, `live_surveys`) in the first row, the state series
(`activated_30d`, `active_30d`, `returned_pct`, `publish_rate`, `collecting_unpublished`) in the
second. Each tile SHALL show the series' label, its current value, the change against the
previous period, a note where the series is a proxy or forward-only, and a line chart of the
series over the selected period. Charts SHALL be drawn with Chart.js loaded from the same CDN
and version the Responses pages use; value and delta SHALL be present in the HTML so the tile
reads without the script.

The current value of an event series SHALL be the last complete ISO week; the running week SHALL
appear on the chart as a distinct final point and SHALL NOT be the compared value. The delta of
an event series SHALL be current minus the preceding week; the delta of a state series SHALL be
the latest snapshot minus the snapshot seven days earlier, when both exist.

#### Scenario: Tiles render for every registry series
- **WHEN** the dashboard loads
- **THEN** there is one tile per series in the registry, in registry order, each with a value
  element, a delta element and a canvas

#### Scenario: Running week is not compared
- **WHEN** it is Wednesday and registrations are 3 this week, 10 last week and 6 the week before
- **THEN** the `regs` tile shows 10 as current and +4 as delta, and the chart's last point is
  the running week's 3, marked partial

#### Scenario: State delta over seven days
- **WHEN** `active_30d` snapshots read 40 today and 36 seven days ago
- **THEN** the tile shows 40 and +4

#### Scenario: Chart data is embedded once
- **WHEN** the dashboard loads
- **THEN** the page contains one JSON script block carrying every tile's series and the Chart.js
  script tag once

### Requirement: State tiles without history
A state tile SHALL never be blank. With no snapshot for its key it SHALL show the live current
value and "history from today"; with fewer than two snapshots it SHALL show the latest value,
no chart and "history from <first snapshot date>"; with two or more it SHALL chart them.

#### Scenario: Deploy day
- **WHEN** the dashboard loads with an empty `MetricSnapshot` table
- **THEN** every state tile shows its live value, no delta and a note that history starts today

#### Scenario: Second day
- **WHEN** one snapshot exists per state series
- **THEN** each state tile shows that value, no canvas and the snapshot's date as history start

### Requirement: Publish moment recorded on the survey
`SurveyHeader` SHALL carry `published_at`, set to the moment of the survey's first transition to
`published` and never changed by later transitions or by publishing a draft as a new version.
Existing surveys SHALL be backfilled from the earliest `AuditLog` `status_transition` row whose
`new_status` is `published`; a survey with no such row SHALL keep `published_at = NULL`. Every
reader that needs a publish moment SHALL fall back to the creation proxy where `published_at` is
`NULL`, as the cohort table did before this change.

#### Scenario: First publish sets it
- **WHEN** a draft survey is transitioned to `published`
- **THEN** `published_at` equals the transition time

#### Scenario: Reopen keeps the first moment
- **WHEN** a published survey is closed and published again
- **THEN** `published_at` is unchanged

#### Scenario: Draft publish keeps it
- **WHEN** a draft copy of a published survey is published as a new version
- **THEN** the canonical survey's `published_at` is unchanged

#### Scenario: Backfill from the audit log
- **WHEN** the backfill runs over a survey with two publish transitions in `AuditLog`
- **THEN** `published_at` equals the earlier row's `created_at`

#### Scenario: No audit row, no guess
- **WHEN** the backfill runs over a published survey with no publish transition in `AuditLog`
- **THEN** `published_at` stays `NULL` and the `Pub ≤14d` column still uses `created_at` for it

## MODIFIED Requirements

### Requirement: Chart period selector
The dashboard SHALL let a staff user trim every chart tile to the most recent 12 or 26 weeks, or
show all, via a `weeks` query parameter, without triggering an admin changelist error. Event
series SHALL show that many ISO weeks; state series SHALL show that many weeks of daily
snapshots; "all" SHALL show every bucket and every snapshot.

#### Scenario: Period selection trims the tiles
- **WHEN** the dashboard is opened with `?weeks=12`
- **THEN** every event tile's series has at most 12 complete weeks plus the running week, every
  state tile's series spans at most 84 days, and the page returns HTTP 200

### Requirement: Weekly signups chart
The dashboard SHALL show real registrations per ISO week as the `regs` tile of the Trends
section, so the summer trough and campaign spikes are visible over time.

#### Scenario: Weekly chart renders
- **WHEN** the dashboard loads
- **THEN** the `regs` tile's series is registrations grouped by `date_trunc('week', date_joined)`,
  most-recent weeks included

#### Scenario: Empty series is handled
- **WHEN** there are no registrations
- **THEN** the tile shows 0, no delta, and the page does not error

### Requirement: Weekly activity chart
The dashboard SHALL show collected responses (non-deleted sessions) per ISO week as the
`responses` tile of the Trends section, as an ongoing-usage signal complementing registrations.

#### Scenario: Activity chart renders
- **WHEN** the dashboard loads
- **THEN** the `responses` tile's series is session counts grouped by
  `date_trunc('week', start_datetime)` over non-deleted sessions

### Requirement: No new data table for the funnel dashboard
The **registration-onward** stages of the funnel SHALL be computed live from existing tables
(`auth_user`, `SurveyHeader`, `SurveySection`, `Question`, `SurveySession`) and SHALL NOT require a
new data-bearing table or a data backfill for those stages. A metadata-only migration for the
display proxy model (no DDL, no table) is permitted.

This constraint applies to everything derivable from our own rows at any past date. It SHALL NOT
apply to the pre-registration acquisition stages, which are not derivable from our tables at all,
nor to **state series** — values such as active creators, returned share or publish rate that
describe the present and cannot be recomputed for a past day because the rows keep only their
latest moment. Those SHALL be persisted daily in `MetricSnapshot` by the `snapshot_metrics`
command, and the dashboard SHALL read that table for their history while still computing their
current value live.

#### Scenario: Dashboard reflects history on first deploy
- **WHEN** the dashboard is deployed for the first time with no prior instrumentation
- **THEN** the registration-onward stages and every event series display the full history
  computed from existing rows, with no backfill step

#### Scenario: No data-bearing schema change for derivable stages
- **WHEN** a stage or series can be computed from existing rows for any past date
- **THEN** it is computed live and no table is added to store it

#### Scenario: Externally sourced stages are persisted locally
- **WHEN** a stage's data exists only in a third-party analytics system
- **THEN** it is stored in a local table by a scheduled sync, and the dashboard reads that table
  instead of calling the provider during a request

#### Scenario: State series are snapshotted
- **WHEN** a series describes the present and its past values cannot be recomputed from rows
- **THEN** its history comes from `MetricSnapshot` rows written once a day, and its current value
  is still computed live

#### Scenario: Forward-only stages state their start date
- **WHEN** a stage, series or breakdown cannot be reconstructed for the period before it began
  recording
- **THEN** the dashboard reports the date recording started rather than presenting the earlier
  period as if it had been measured
