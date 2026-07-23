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

### Requirement: Goals vs plan targets
The dashboard SHALL show the current values of the North-Star and supporting metrics against
their GTM-plan targets, each as a card with a progress bar and a colour tone (green on-track,
amber behind, red off-track). Metrics: activated creators (published + ≥5 responses) in the last
30 days, registrations in the last 30 days, all-time publish rate, and attribution coverage.

#### Scenario: Goal cards render with progress toward target
- **WHEN** the dashboard loads
- **THEN** four goal cards render, each showing current value, target, a percent-to-target, and a
  coloured progress bar

### Requirement: Cluster radar
The dashboard SHALL surface likely classroom/team clusters early: a temporal signup burst
(≥5 registrations within any 48-hour window in the recent past) and a same-institutional-domain
group (≥3 registrations on one non-freemail email domain within 30 days). Each detected cluster
SHALL be shown as an alert with a link to the accounts; when none are detected an empty state is shown.

#### Scenario: Burst detected
- **WHEN** at least 5 real registrations occur within a 48-hour window in the recent period
- **THEN** the radar shows a burst alert with the count

#### Scenario: Domain cluster detected
- **WHEN** at least 3 recent real registrations share one non-freemail email domain
- **THEN** the radar shows a domain-cluster alert naming that domain

#### Scenario: All quiet
- **WHEN** no burst and no domain cluster is present
- **THEN** the radar shows an empty state, not an error

### Requirement: Abuse summary
The dashboard SHALL show the number of bot registrations blocked in the last 7 days and the top
offending IPs, sourced from `AbuseEvent`.

#### Scenario: Abuse widget renders
- **WHEN** the dashboard loads
- **THEN** it shows the 7-day blocked count and up to five top IPs by attempt count

### Requirement: Time-boxed cohort columns
The cohort funnel SHALL include time-boxed columns so young and old cohorts are comparable:
published within 14 days of signup, and reached ≥5 responses within 30 days of signup.

#### Scenario: In-window creators only
- **WHEN** a creator publishes or reaches 5 responses only after the respective window
- **THEN** they are NOT counted in the time-boxed column, even though they count in the all-time stage

### Requirement: Time-to-value medians
The dashboard SHALL show median days from registration to first survey, to first publish, and to
first response.

#### Scenario: Medians render
- **WHEN** the dashboard loads
- **THEN** it shows three median-days figures (or a dash when a stage has no data)

### Requirement: Top active surveys
The dashboard SHALL list the top surveys by response volume in the last 30 days (the currently
active ones), showing survey name, owner, status, and recent response count, with a deep link to
the survey in the admin.

#### Scenario: Ranked by recent responses
- **WHEN** several surveys have collected responses in the last 30 days
- **THEN** they are listed most-active first, and a survey with only older responses is excluded

#### Scenario: Bounded list
- **WHEN** more than ten surveys are active
- **THEN** at most ten are shown

### Requirement: Action lists
The dashboard SHALL show two actionable lists with deep links into the admin: institutional-domain
registrants who never created a survey (outreach candidates), and surveys collecting responses
while still draft/testing (publish-nudge candidates).

#### Scenario: Dormant valuable list
- **WHEN** a registrant has a non-freemail email domain and owns no survey
- **THEN** they appear in the dormant-valuable list with a link to their admin page

#### Scenario: Collecting-but-unpublished list
- **WHEN** a draft or testing survey has at least one non-deleted response
- **THEN** it appears in the collecting-but-unpublished list with a link to the survey

### Requirement: Chart period selector
The dashboard SHALL let a staff user trim the two weekly charts to the most recent 12 or 26 weeks,
or show all weeks, via a `weeks` query parameter, without triggering an admin changelist error.

#### Scenario: Period selection trims the charts
- **WHEN** the dashboard is opened with `?weeks=12`
- **THEN** the weekly charts show only the most recent 12 weeks and the page returns HTTP 200

### Requirement: Registrations-by-source (placeholder until attribution)
The dashboard SHALL show a registrations-by-source panel. Until signup attribution ships
(Phase 1), it SHALL clearly indicate that source data is not yet available rather than fabricate sources.

#### Scenario: Placeholder before Phase 1
- **WHEN** signup attribution is not yet live
- **THEN** the source panel shows recent registrations under a single unknown/direct bucket with a
  note that it needs Phase 1

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
