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

### Requirement: Weekly signups series
The dashboard SHALL show a weekly time series of real registration counts so the summer trough
and campaign spikes are visible over time.

#### Scenario: Weekly counts render
- **WHEN** the dashboard loads
- **THEN** it shows registrations grouped by `date_trunc('week', date_joined)`, most-recent weeks included

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
