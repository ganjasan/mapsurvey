## ADDED Requirements

### Requirement: Metric series registry
The system SHALL define the staff dashboard's time series in one registry, `survey/metrics.py`,
as an ordered tuple of `Series(key, label, kind, unit, note)` where `kind` is `event` (computed
live from timestamps on existing rows, bucketed by ISO week) or `state` (a point-in-time value
that is snapshotted daily). The dashboard, the snapshot command and the tests SHALL iterate the
same tuple; no second list of metric keys SHALL exist.

The registry SHALL contain the event series `regs`, `activations`, `surveys_created`,
`surveys_published`, `first_responses`, `responses`, `live_surveys` and the state series
`activated_30d`, `active_30d`, `returned_pct`, `publish_rate`, `collecting_unpublished`. A state
series' current value SHALL come from the same computation the dashboard already shows for that
number (`CreatorFunnelService.goals`, `active_user_metrics`, `collecting_unpublished`), never
from a parallel definition.

#### Scenario: Event series bucket by ISO week
- **WHEN** `weekly_series('regs', start, end)` is computed over users who joined on a Sunday and
  the following Monday
- **THEN** the two land in different buckets, each keyed by its Monday, and staff/superuser
  accounts are not counted

#### Scenario: Surveys-created counts canonical rows only
- **WHEN** a creator has a canonical survey, a draft copy of it and an archived version
- **THEN** `surveys_created` counts one survey in the week of the canonical row's `created_at`

#### Scenario: First responses are per survey and external
- **WHEN** a survey's earliest non-deleted session was opened by its owner and its earliest
  `external` session a week later
- **THEN** `first_responses` counts that survey in the later week

#### Scenario: Live surveys count distinct surveys
- **WHEN** one survey collects five sessions in a week and another collects one
- **THEN** `live_surveys` is 2 for that week and `responses` is 6

#### Scenario: State series reuse the dashboard's computation
- **WHEN** `current_state('activated_30d')` is computed
- **THEN** it equals the value shown on the "Activated creators · 30d" goal card for the same
  instant

### Requirement: MetricSnapshot table
The system SHALL have a `MetricSnapshot` model with `date` (DateField), `key` (CharField, a
registry key) and `value` (FloatField), unique per `(date, key)` and indexed on `(key, date)`.
Rows SHALL be written only by the `snapshot_metrics` command; the admin SHALL expose the table
read-only (list and filter by key, no add or change).

#### Scenario: One row per day and key
- **WHEN** two rows with the same `date` and `key` are inserted
- **THEN** the second insert is rejected by the unique constraint

#### Scenario: Read-only in the admin
- **WHEN** a staff user opens the MetricSnapshot admin
- **THEN** the list renders and there is no add or change form

### Requirement: Daily snapshot command
The system SHALL provide a management command `snapshot_metrics` that computes the current value
of every `state` series in the registry and writes it for today's date, creating or overwriting
the row for `(today, key)`. An optional `--date YYYY-MM-DD` SHALL write the rows under that date
instead, from the current state. The command SHALL let an exception propagate so a failed run is
visible to the scheduler. A Render cron `mapsurvey-metrics-snapshot` SHALL run it once a day
shortly after midnight UTC.

#### Scenario: One run writes every state series
- **WHEN** `snapshot_metrics` runs on an empty table
- **THEN** there is exactly one `MetricSnapshot` row dated today for each state series in the
  registry

#### Scenario: A rerun on the same day overwrites
- **WHEN** `snapshot_metrics` runs twice on the same day with a changed underlying value in between
- **THEN** the table holds one row per state series for that date, carrying the later value

#### Scenario: Explicit date
- **WHEN** `snapshot_metrics --date 2026-10-01` runs
- **THEN** the rows are dated 2026-10-01 and the values are the current state

### Requirement: Snapshot history reads
The system SHALL provide `snapshot_series(key, start, end)` returning the `(date, value)` points
of a state series within the range, oldest first, and `history_since(key)` returning the date of
the earliest snapshot for the key or `None` when there is none.

#### Scenario: Range read
- **WHEN** snapshots exist for a key on ten consecutive days and the range covers the last seven
- **THEN** seven points are returned, oldest first

#### Scenario: No history
- **WHEN** no snapshot exists for a key
- **THEN** `snapshot_series` returns an empty list and `history_since` returns `None`
