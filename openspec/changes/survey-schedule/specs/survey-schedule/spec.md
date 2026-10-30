## ADDED Requirements

### Requirement: A survey has an optional period
A survey SHALL carry two optional instants, `opens_at` and `closes_at` (stored in UTC), and a
`schedule_timezone` (an IANA zone name, blank meaning UTC) that records the clock the creator
entered them in. Each end SHALL be settable alone. The period SHALL live on the canonical survey
only: unpublished changes, archived versions and the draft copy SHALL read it through
`canonical_of()` and SHALL never hold a period of their own. A save SHALL refuse a `closes_at`
that is not after `opens_at`, and SHALL refuse a `closes_at` that is **changed** to an instant in
the past; an unchanged past `closes_at` (the time of a close that already happened) SHALL pass, so
later Settings saves keep working. Every display of either instant — the Settings panel, the
publishing widget, the respondent's "opens on" page — SHALL format it in `schedule_timezone`.

#### Scenario: Only an end date
- **WHEN** a creator saves "Closes on 1 Nov 2026 23:59" with no opening time, in zone Europe/Berlin
- **THEN** `closes_at` is `2026-11-01T22:59:00Z`, `opens_at` is empty, `schedule_timezone` is
  `Europe/Berlin`, and the panel shows "1 Nov 2026, 23:59 (Europe/Berlin)"

#### Scenario: End before start is refused
- **WHEN** a creator saves an opening time of 10 Nov and a closing time of 1 Nov
- **THEN** the save fails on `closes_at` with a message that the survey must close after it opens
  and nothing is written

#### Scenario: A new closing time in the past is refused
- **WHEN** a creator changes `closes_at` to yesterday
- **THEN** the save fails on `closes_at` asking for a time in the future

#### Scenario: An old closing time survives a later save
- **GIVEN** a survey closed automatically yesterday, `closes_at` still holding yesterday
- **WHEN** the creator saves another Settings field without touching the period
- **THEN** the save succeeds and `closes_at` is unchanged

#### Scenario: Unpublished changes read the live period
- **GIVEN** a published survey with `closes_at` set and unpublished changes started
- **WHEN** the period is read on the draft copy
- **THEN** it is the canonical survey's period, and publishing the draft leaves it unchanged

### Requirement: The period is set in Settings
The survey's Settings panel SHALL offer a "Survey period" block with "Opens on" and "Closes on"
`datetime-local` inputs, saved through the Settings autosave form and
`services.surveys.update_settings`, and SHALL send the browser's zone as `schedule_timezone`.
The block SHALL state the zone the times are read in. The publishing widget SHALL show the next
scheduled event of a `published` survey — "Opens <date, time>" before `opens_at`, "Closes <date,
time>" before `closes_at` — and nothing when no event is ahead. Both inputs SHALL be owner-only
controls like the rest of Settings and SHALL obey the Settings lock of a trashed survey.

#### Scenario: Period saved from the panel
- **WHEN** an owner fills both inputs in the Settings panel and the autosave posts
- **THEN** the survey holds the two instants, the browser's zone is recorded, and the panel's
  indicator reads "All changes saved"

#### Scenario: Widget shows the next event
- **GIVEN** a published survey with `closes_at` two days ahead and no `opens_at`
- **WHEN** an owner opens the editor
- **THEN** the publishing widget reads "Open · v1" and, beneath it, "Closes <date>, <time>"

#### Scenario: Clearing an input clears the instant
- **WHEN** the owner empties "Closes on" and the panel saves
- **THEN** `closes_at` is `NULL` and the widget shows no closing event

### Requirement: Respondents see the period, to the minute
On a `published` survey, `check_survey_access` SHALL compare the current time with the canonical
survey's period. Before `opens_at` it SHALL render the "opens on" page
(`survey_not_yet_open.html`) with status `200`, `X-Robots-Tag: noindex`, the survey's name and the
opening time in `schedule_timezone`, and SHALL create no `SurveySession`. At or after `closes_at`
it SHALL render the existing closed page exactly as a `closed` survey gets, whether or not the
periodic task has run. Between the two it SHALL behave as a published survey does today. Editors
and owners SHALL bypass the period as they bypass every other access rule. A `testing` survey
SHALL ignore the period. A held survey (content review) SHALL keep its `404` whatever the period.

#### Scenario: Before the opening time
- **GIVEN** a published survey with `opens_at` tomorrow
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` and its first section
- **THEN** both answer `200` with the "opens on" page naming the survey and tomorrow's time in
  the survey's zone, carry `X-Robots-Tag: noindex`, and no `SurveySession` row exists afterwards

#### Scenario: After the closing time, before the job
- **GIVEN** a published survey with `closes_at` one minute ago and the periodic task not yet run
- **WHEN** an anonymous visitor requests the survey
- **THEN** the response is the closed page, byte-for-byte the one a `closed` survey renders

#### Scenario: A section POST after the closing time
- **GIVEN** a respondent who opened the survey before `closes_at` and submits a section after it
- **THEN** the POST is answered with the closed page and no answers are stored

#### Scenario: Editors walk through regardless
- **GIVEN** a published survey with `opens_at` tomorrow
- **WHEN** a collaborator with the `editor` role opens it
- **THEN** they see the first section as usual

#### Scenario: Testing ignores the period
- **GIVEN** a `testing` survey with `opens_at` tomorrow
- **WHEN** a tester opens it with the test token
- **THEN** they see the first section

### Requirement: The close happens through the lifecycle service
A periodic Celery task SHALL close due surveys: `survey.tasks.apply_survey_schedule`, scheduled
every five minutes by Celery beat embedded in the worker, closes every canonical, non-deleted `published` survey
whose `closes_at` is at or before now by calling `services.publishing.transition(Actor(user=None,
surface='schedule'), survey, 'closed')`, one survey per transaction, locking the row with
`skip_locked` so overlapping runs never process a survey twice. The resulting `AuditLog` row SHALL
be the ordinary `status_transition` with `old_status='published'`, `new_status='closed'` and
`scheduled=True` in its metadata. A survey whose transition is refused or raises SHALL be logged
and skipped, never block the others. The same function SHALL be callable as the management
command `apply_survey_schedule`.

#### Scenario: Due survey is closed within one interval
- **GIVEN** a published survey whose `closes_at` passed two minutes ago
- **WHEN** the task runs
- **THEN** the survey's status is `closed`, an `AuditLog` row `status_transition` with
  `scheduled=True` and no actor exists, and the editor shows it as Closed with a Reopen button

#### Scenario: Not yet due, not published, not canonical
- **GIVEN** a published survey closing tomorrow, a `testing` survey closing yesterday, a draft
  copy of a survey closing yesterday, and a trashed survey closing yesterday
- **WHEN** the task runs
- **THEN** none of them changes status

#### Scenario: One failure does not stop the pass
- **GIVEN** two due surveys, the first of which raises inside `transition`
- **WHEN** the task runs
- **THEN** the second is closed and the first is logged

#### Scenario: Management command
- **WHEN** `python manage.py apply_survey_schedule` runs with one due survey
- **THEN** it closes that survey and prints how many it closed

### Requirement: Reopening by hand is final
`transition()` SHALL, when it moves a survey from `closed` to `published` and `closes_at` is at
or before now, clear `closes_at` (and an `opens_at` that is also in the past), recording one
`AuditLog` row `schedule_cleared` with the cleared instants, so the periodic task cannot close it
again. A `closes_at` in the future SHALL be kept on reopen. This rule SHALL apply on every surface
that reopens: the editor, `POST /api/v1/surveys/{uuid}/publish`, the MCP `publish_survey` tool.

#### Scenario: Reopen after an automatic close
- **GIVEN** a survey closed by the task yesterday
- **WHEN** the owner presses Reopen and the task runs again
- **THEN** the survey stays `published`, `closes_at` is `NULL`, and an `AuditLog` row
  `schedule_cleared` names the cleared time

#### Scenario: Early manual close keeps the plan
- **GIVEN** a published survey closing next week, closed by hand today
- **WHEN** the owner reopens it
- **THEN** `closes_at` still holds next week's time and the task closes it then

### Requirement: The period over the API and the MCP server
`SurveyOut` SHALL carry `opens_at`, `closes_at` (ISO 8601 in UTC or `null`) and
`schedule_timezone`; `SurveyPatchIn` SHALL accept all three (datetimes with an offset, or a naive
value read in `schedule_timezone`), validated by the Settings form so the refusals are the same
`422 validation` naming the field. The MCP `update_survey` tool SHALL accept them through the
shared schema and the generated API and MCP references SHALL describe them.

#### Scenario: Set the period over REST
- **WHEN** an owner token PATCHes `{"closes_at": "2026-11-01T23:59:00+01:00",
  "schedule_timezone": "Europe/Berlin"}`
- **THEN** the response shows `closes_at: "2026-11-01T22:59:00Z"` and the survey closes then

#### Scenario: End before start over REST
- **WHEN** a PATCH sets `opens_at` after `closes_at`
- **THEN** the response is `422 validation` naming `closes_at`

### Requirement: Copies and backups leave the period behind
Duplicating a survey, exporting it as a survey file (ZIP) and importing one SHALL NOT carry
`opens_at`, `closes_at` or `schedule_timezone`; a copy starts with no period.

#### Scenario: Duplicate has no period
- **GIVEN** a survey closing next week
- **WHEN** it is duplicated
- **THEN** the copy has no `opens_at`, no `closes_at` and an empty zone

#### Scenario: Backup round trip
- **WHEN** a survey with a period is exported as a ZIP and imported
- **THEN** the `survey.json` carries no period keys and the imported survey has none
