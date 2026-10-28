## ADDED Requirements

### Requirement: Persisted per-user last-activity timestamp

The system SHALL persist, for each registered user, the most recent time that
user made an authenticated request, in a `UserActivity` record holding a
`OneToOneField` to the user and an indexed `last_activity` datetime. The value
SHALL be updated by middleware on authenticated requests and SHALL be queryable
across all users for reporting.

#### Scenario: Authenticated request records activity

- **WHEN** a logged-in user makes an authenticated request and no throttle marker
  is present for them
- **THEN** their `UserActivity.last_activity` is set to the current time,
  creating the `UserActivity` row if it did not exist.

#### Scenario: Anonymous request records nothing

- **WHEN** an unauthenticated request is handled
- **THEN** no `UserActivity` row is created or updated.

#### Scenario: Writes are throttled

- **WHEN** a logged-in user makes multiple authenticated requests within the
  throttle window (default 300 seconds)
- **THEN** `UserActivity.last_activity` is written at most once for that window
  (subsequent requests within the window do not write), and a request after the
  window elapses writes again.

#### Scenario: Activity update never breaks the request

- **WHEN** the activity write fails (e.g. database error) while handling an
  otherwise valid request
- **THEN** the request is still served normally; the failure is swallowed.

### Requirement: Funnel activity metrics use last-activity

The funnel dashboard's creator activity metrics SHALL treat `last_activity` as a
creator action. A user's "returned" status and the `active_7/30/90` windows SHALL
consider the most recent of the user's `last_login`, latest owned
`SurveyHeader.updated_at`, and `last_activity` (plus, for the active windows, the
latest non-deleted response on their surveys). Users without a `UserActivity` row
SHALL fall back to the pre-existing signals and SHALL NOT be reclassified as less
active than before.

#### Scenario: Live-session builder counts as returned

- **WHEN** a user registered days ago, whose `last_login` is unchanged since
  registration and who has not saved any parent survey, makes an authenticated
  request today (recording `last_activity` today)
- **THEN** the funnel classifies them as "returned" and within the active
  windows, based on `last_activity`.

#### Scenario: Legacy user without a UserActivity row is unaffected

- **WHEN** the metrics are computed for a user who has no `UserActivity` row
- **THEN** their "returned"/active classification is exactly what it was from
  `last_login`, `SurveyHeader.updated_at`, and their latest response.
