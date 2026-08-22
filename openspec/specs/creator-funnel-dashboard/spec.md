# creator-funnel-dashboard Specification

## Purpose
TBD - created by archiving change funnel-monitoring. Update Purpose after archive.
## Requirements
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
the counts that reached each activation stage: **activated the account (`is_active=True`), logged
in at least once (`last_login` set),** created a survey, added at least one question, published a
survey, and collected at least 1 / 5 / 10 non-deleted responses. The activated and logged-in
stages SHALL appear between registrations and created-survey, in both the cohort table and the
all-time totals. Real registrations SHALL exclude staff and superuser accounts.

#### Scenario: Cohort rows reflect existing data
- **WHEN** the service aggregates registrations grouped by `date_trunc('month', date_joined)`
- **THEN** each cohort row reports registrations and the per-stage counts derived from
  `auth_user.is_active`, `auth_user.last_login`, `SurveyHeader`, its `Question` rows,
  `SurveyHeader.status`, and non-deleted `SurveySession` counts

#### Scenario: Activated stage counts active accounts
- **WHEN** the cohort funnel is computed
- **THEN** a user with `is_active=True` counts in their signup cohort's activated stage, and a
  user with `is_active=False` does not

#### Scenario: Logged-in stage counts users who ever signed in
- **WHEN** the cohort funnel is computed
- **THEN** a user with a non-null `last_login` counts in their signup cohort's logged-in stage,
  and a user who never logged in does not

#### Scenario: All-time totals include the new stages
- **WHEN** the all-time totals row is computed
- **THEN** it includes summed activated and logged-in counts alongside the existing stages

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
The **registration-onward** stages of the funnel SHALL be computed live from existing tables
(`auth_user`, `SurveyHeader`, `SurveySection`, `Question`, `SurveySession`) and SHALL NOT require a
new data-bearing table or a data backfill for those stages. A metadata-only migration for the
display proxy model (no DDL, no table) is permitted.

This constraint applies to everything derivable from our own rows. It SHALL NOT apply to the
pre-registration acquisition stages, which are not derivable from our tables at all: impressions and
landing visits exist only inside third-party systems, and a staff page must not call those APIs
during a request. Those metrics SHALL therefore be persisted locally by an out-of-band sync, and the
respondent-identity needed to split demo opens SHALL live in its own table rather than being added to
`SurveySession`.

#### Scenario: Dashboard reflects history on first deploy
- **WHEN** the dashboard is deployed for the first time with no prior instrumentation
- **THEN** the registration-onward stages display the full historical funnel computed from existing
  rows, with no backfill step

#### Scenario: No data-bearing schema change for derivable stages
- **WHEN** a stage can be computed from existing rows
- **THEN** it is computed live and no table is added to store it

#### Scenario: Externally sourced stages are persisted locally
- **WHEN** a stage's data exists only in a third-party analytics system
- **THEN** it is stored in a local table by a scheduled sync, and the dashboard reads that table
  instead of calling the provider during a request

#### Scenario: Forward-only stages state their start date
- **WHEN** a stage or breakdown cannot be reconstructed for the period before it began recording
- **THEN** the dashboard reports the date recording started rather than presenting the earlier period
  as if it had been measured

### Requirement: Top-of-funnel acquisition block

The dashboard SHALL render a section, positioned above the registration-onward stages, showing for
a selected date window: Google impressions, landing visits, registrations, and demo opens. Each
stage SHALL display its absolute count and, except for the first, its conversion rate from the
preceding stage. The section SHALL state the date window it covers and name the source of each
stage.

#### Scenario: The four stages render with conversions

- **WHEN** a staff user opens the dashboard with all sources synchronised
- **THEN** the acquisition section shows impressions, landing visits, registrations, and demo opens
  for the window, with a conversion percentage between each consecutive pair

#### Scenario: Registrations agree with the cohort funnel

- **WHEN** the registrations stage is computed for a window
- **THEN** it counts the same real registrations (staff and superusers excluded) that the cohort
  funnel counts for that period

#### Scenario: The window and sources are stated

- **WHEN** the acquisition section renders
- **THEN** it states the covered date range and identifies which stage comes from Search Console,
  which from Plausible, and which from our own database

#### Scenario: Cross-source ratios are labelled as such

- **WHEN** conversion percentages between stages are shown
- **THEN** the section indicates that they combine separate measurement systems and do not track
  individual visitors through the funnel

### Requirement: Acquisition stages reflect source availability

Each acquisition stage SHALL be rendered from locally stored metrics only. A stage whose source is
not configured, has never synchronised, or has no data for the window SHALL render as unavailable
with the reason, and SHALL NOT render as zero. Any conversion rate depending on an unavailable
stage SHALL also render as unavailable.

#### Scenario: A source is not configured

- **WHEN** the dashboard renders while a provider has no credentials configured
- **THEN** that provider's stages show a not-configured note instead of a number, and the remaining
  stages and the rest of the dashboard render normally

#### Scenario: A source is configured but failing

- **WHEN** a provider's last synchronisation failed
- **THEN** the section shows that the data is stale, how old the last successful synchronisation is,
  and the reported failure

#### Scenario: A missing stage does not fabricate a conversion

- **WHEN** landing visits are unavailable for the window
- **THEN** the impressions-to-visits and visits-to-registrations rates render as unavailable rather
  than as 0% or as a rate computed against a missing value

#### Scenario: An empty but healthy window shows zero

- **WHEN** a source synchronised successfully and genuinely recorded no activity in the window
- **THEN** the stage shows zero, distinguishable from the unavailable state

### Requirement: Demo opens reported as total plus authentication split

The dashboard SHALL report demo opens as a total derived from all non-deleted sessions on the demo
survey, and separately as anonymous versus signed-in counts derived from recorded demo-open
entries. The split SHALL state the date from which it has been recorded, and SHALL NOT be presented
as covering sessions that predate that date.

#### Scenario: Total covers full history

- **WHEN** the demo total is computed for a window predating the split's start
- **THEN** it counts the demo survey's non-deleted sessions in that window

#### Scenario: The split is bounded by its start date

- **WHEN** the anonymous and signed-in counts are shown
- **THEN** the section states the date recording began, and does not attribute earlier sessions to
  either group

#### Scenario: The demo survey is identified

- **WHEN** the demo panel renders with a resolvable demo survey
- **THEN** it names the survey the numbers refer to

#### Scenario: The demo survey cannot be resolved

- **WHEN** the demo survey URL is unset or points at a survey that no longer exists
- **THEN** the demo stage renders as not configured and the rest of the dashboard renders normally

### Requirement: Acquisition channel breakdown

The dashboard SHALL show landing visits broken down by referrer channel for the selected window,
ordered by volume, so the traffic mix behind the visits stage is visible.

#### Scenario: Channels are listed by volume

- **WHEN** the window contains visits from several referrer channels
- **THEN** each channel is listed with its visit count, ordered from largest to smallest

#### Scenario: No channel data available

- **WHEN** the channel source is unavailable for the window
- **THEN** the breakdown renders as unavailable with the reason, and the rest of the section still
  renders

### Requirement: Synchronisation freshness is visible on the dashboard

The dashboard SHALL show, per external source, when it last synchronised successfully, so that a
silently stalled scheduled job is apparent to whoever reads the numbers.

#### Scenario: Freshness is shown next to the numbers

- **WHEN** the acquisition section renders with at least one configured source
- **THEN** it shows the age of that source's last successful synchronisation

#### Scenario: Stale data is flagged

- **WHEN** a configured source has not synchronised successfully for longer than the expected
  interval
- **THEN** the section marks that source's data as stale
