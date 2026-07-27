# creator-funnel-dashboard Specification (delta)

## MODIFIED Requirements

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
