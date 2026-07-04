## ADDED Requirements

### Requirement: Staff-only creator funnel dashboard page
The system SHALL provide a Django-admin page, accessible only to staff users, that renders the
platform-wide creator acquisition→activation funnel. Non-staff and anonymous requests SHALL be
denied access by the standard admin authentication.

#### Scenario: Staff user opens the dashboard
- **WHEN** a user with `is_staff=True` opens the funnel dashboard admin URL
- **THEN** the page renders with the cohort funnel table, weekly signups series, and all-time totals

#### Scenario: Non-staff user is denied
- **WHEN** an authenticated non-staff user requests the funnel dashboard admin URL
- **THEN** the system responds with the admin login/permission-denied flow and shows no funnel data

#### Scenario: Anonymous user is denied
- **WHEN** an unauthenticated request hits the funnel dashboard admin URL
- **THEN** the system redirects to the admin login and shows no funnel data

### Requirement: Monthly cohort activation funnel
The dashboard SHALL show, for each registration-month cohort, the count of real registrations and
the counts that reached each activation stage: created a survey, added at least one question,
published a survey, and collected at least 1 / 5 / 10 non-deleted responses. Real registrations
SHALL exclude staff and superuser accounts.

#### Scenario: Cohort rows reflect existing data
- **WHEN** the service aggregates registrations grouped by `date_trunc('month', date_joined)`
- **THEN** each cohort row reports registrations and the per-stage counts derived from
  `SurveyHeader`, its `Question` rows, `SurveyHeader.status`, and non-deleted `SurveySession` counts

#### Scenario: Staff and superusers are excluded
- **WHEN** the registration population is computed
- **THEN** users with `is_staff=True` or `is_superuser=True` are not counted in any cohort or stage

#### Scenario: Published stage counts only published-or-later surveys
- **WHEN** the published stage is computed
- **THEN** only creators owning a survey with `status` in (`published`, `closed`, `archived`) are counted

#### Scenario: Deleted sessions are not counted as responses
- **WHEN** response-count stages (≥1/≥5/≥10) are computed
- **THEN** `SurveySession` rows with `is_deleted=True` are excluded from the counts

### Requirement: Dashboard embedded on the admin home page
The admin index (Home) SHALL render the funnel dashboard content above the standard app list,
so the growth picture is the first thing a staff user sees. The standalone dashboard page SHALL
remain available as a deep link.

#### Scenario: Admin home shows the funnel
- **WHEN** a staff user opens the admin index
- **THEN** the funnel dashboard content renders above the app list, and the app list is still present

#### Scenario: Standalone page still works
- **WHEN** a staff user opens the funnel dashboard changelist URL directly
- **THEN** the dashboard page renders as before

### Requirement: Weekly signups chart
The dashboard SHALL show a weekly time series of real registration counts as an inline chart
(no external chart library or CDN) so the summer trough and campaign spikes are visible over time.

#### Scenario: Weekly chart renders
- **WHEN** the dashboard loads
- **THEN** it shows registrations grouped by `date_trunc('week', date_joined)` as an inline-SVG
  bar chart, most-recent weeks included, with sparse x-axis week labels

#### Scenario: Empty series is handled
- **WHEN** there are no registrations
- **THEN** the chart area shows an empty-state message and does not error

### Requirement: Weekly activity chart
The dashboard SHALL show a weekly time series of collected responses (non-deleted sessions) as an
inline chart, as an ongoing-usage signal complementing registrations.

#### Scenario: Activity chart renders
- **WHEN** the dashboard loads
- **THEN** it shows response counts grouped by `date_trunc('week', start_datetime)` over non-deleted
  sessions as an inline-SVG bar chart

### Requirement: Living-users (active creator) metrics
The dashboard SHALL show how many registered creators are still using the platform. A creator's
activity time is the most recent of: last login, last edit to any survey they own, and the latest
non-deleted response on any of their surveys. The dashboard SHALL report counts (and % of total)
for: active within 7 / 30 / 90 days; `returned`; and `dormant`. `returned` SHALL be based only on
the creator's own actions (login or survey edit) occurring on a day after registration — a
respondent's answer SHALL NOT by itself mark a creator as returned. `dormant` is the complement of
`returned`.

#### Scenario: Active windows counted
- **WHEN** a creator's most recent activity falls within a rolling window (7/30/90 days)
- **THEN** they are counted in that window's active total

#### Scenario: Returned requires a creator action after signup
- **WHEN** the only post-registration activity on a creator's surveys is a respondent's answer
  (no later login and no survey edit)
- **THEN** the creator is NOT counted as returned (they are counted as dormant)

#### Scenario: Returned via later login or edit
- **WHEN** a creator logs in or edits a survey on a day after they registered
- **THEN** they are counted as returned

#### Scenario: Percentages are of the real-registration total
- **WHEN** the metrics render
- **THEN** each block shows a count and its percentage of the total real registrations

### Requirement: No new data table for the funnel dashboard
The funnel dashboard SHALL compute all stages live from existing tables (`auth_user`,
`SurveyHeader`, `SurveySection`, `Question`, `SurveySession`) and SHALL NOT create any new
data-bearing table or require any data backfill. A metadata-only migration for the display proxy
model (no DDL, no table) is permitted.

#### Scenario: Dashboard reflects history on first deploy
- **WHEN** the dashboard is deployed for the first time with no prior instrumentation
- **THEN** it displays the full historical funnel computed from existing rows, with no backfill step

#### Scenario: No data-bearing schema change
- **WHEN** the change is applied
- **THEN** no new table storing rows is created (only a proxy model whose migration performs no DDL)
