## Context

A survey's status is changed by people: `services.publishing.transition()` is the one write path
(spec `survey-service-layer`), the editor's publishing widget and the REST `/close` route call it,
and `check_survey_access` turns `status` into what a respondent sees (`survey-access-control`).
Nothing in the system runs on a clock except the daily Render cron `reclaim.sh`; the Celery worker
exists (one instance in production and on previews) but has no beat loop. No creator time zone is
stored anywhere.

Issue #497 asks for an end date; the owner widened it to a **period** ("from … to …", 2026-10-30)
and chose the semantics for the start: *published, but closed until the date* — the survey is
published by hand, the gate holds the door. Automatic opening by status change (scheduled publish)
was considered and rejected: publishing runs content screening, asks the creator to acknowledge
translation gaps, attributes `survey_published` to a person and may hold the survey for review;
none of that belongs in a cron.

## Goals / Non-Goals

**Goals:**
- A creator sets "Opens on" and "Closes on" once, in Settings, in their own clock, and the survey
  behaves accordingly to the minute without anyone remembering the date.
- An automatic close is indistinguishable from a manual one on every creator surface: same status,
  same `AuditLog` action, same closed page, same Reopen button.
- Reopening by hand is final until the creator sets a new date.
- The same fields through the REST API and the MCP server, validated by the same form.

**Non-Goals:**
- Scheduled publishing (status change at `opens_at`).
- A "closes on …" line on the respondent's first page (issue listed it as optional; the respondent
  surfaces are left untouched — the owner's standing rule for that flow).
- Recurring periods, time windows per day, per-section schedules.
- A creator-level time zone preference; the zone travels with the survey.
- Notifying the creator when the survey closes (a later change can hook the audit row).

## Decisions

### 1. The gate reads the dates; the job materialises the status
`check_survey_access` compares `now` with the canonical survey's `opens_at`/`closes_at` on a
`published` survey, so a respondent who arrives one second after the close sees the closed page
whatever the job's cadence. The periodic task then performs the real `transition(…, 'closed')`
within its interval, which is what gives the audit row and the status creators see.

*Alternative — job only*: simpler, but a five-minute window in which the survey is "closed" for
the creator's announcement and open for respondents, and a daily cron would make that a day.
*Alternative — gate only*: exact, but the dashboard would say "Open" for a survey that no longer
takes answers, and nothing would be audited. Both halves are needed; the gate is the contract for
respondents, the job for creators.

### 2. Opening never changes status
Before `opens_at`, a `published` survey renders `survey_not_yet_open.html` (`200`, `noindex`,
names the survey and the opening time in the survey's zone, creates no `SurveySession`). The
status stays `published`, so the publish moment (screening, gaps, event) remains the creator's
click. A `testing` survey ignores the period: testers must be able to walk through it at any time.

Status `200` rather than `404`: this page is meant to be found and read ("come back on Monday");
the `404` rule in `survey-access-control` exists to make drafts indistinguishable from nothing,
which does not apply to a survey the creator has announced. `noindex` keeps the placeholder out
of search results.

### 3. Reopen clears a past `closes_at`, keeps a future one
In `transition()`, on `closed → published`: if `closes_at` is set and `<= now`, it is cleared (and
`opens_at` too if it is in the past, so the period reads clean) with one `audit` row
`schedule_cleared`. A `closes_at` in the future is kept — the creator closed early by hand and the
period still stands. This is one rule in the service, so the editor, REST `/publish` and MCP
behave alike, and the job (which only picks `status='published' AND closes_at <= now`) cannot
re-close a reopened survey.

*Alternative — clear on every reopen*: loses a deliberate future date. *Alternative — a flag
"auto_closed_at"*: a second source of truth the UI would have to explain.

### 4. Celery beat embedded in the worker
`celery -A mapsurvey worker -B -s /tmp/celerybeat-schedule`; `CELERY_BEAT_SCHEDULE` runs
`survey.tasks.apply_survey_schedule` every five minutes. One worker instance exists, so an
embedded beat cannot double-fire; the `render.yaml` comment says that scaling the worker to two
instances means moving beat into its own service. The task is idempotent and safe under overlap:
it locks due rows `select_for_update(skip_locked=True)` and `transition()` refuses a survey that
is no longer `published`. A management command `apply_survey_schedule` wraps the same function
for ops and for a preview whose worker is asleep.

*Alternative — a Render cron every five minutes*: each run boots the Docker image (~40 s) and is
billed; 288 boots a day for a query that usually returns nothing. *Alternative — the daily
`reclaim.sh`*: "closed within a day" fails the acceptance criterion and the creator's expectation.

### 5. Time zone travels with the survey
Two UTC `DateTimeField`s plus `schedule_timezone` (IANA name, blank = UTC). The Settings panel
uses `datetime-local` inputs and a hidden `schedule_timezone` filled from
`Intl.DateTimeFormat().resolvedOptions().timeZone`; `SurveyHeaderForm.clean()` interprets a naive
value in that zone and an aware value (REST, ISO 8601 with offset) as given. Every display — the
publishing widget, the "opens on" page, API output — formats in `schedule_timezone`, so a creator
in Bishkek and their colleague in Berlin read the same wall-clock time the creator typed.

*Alternative — a creator preference*: two creators of one survey would see different times;
also a new preferences surface for one feature.

### 6. Validation lives in the form, like every Settings rule
`closes_at` must be after `opens_at`; a **changed** `closes_at` must be in the future (an unchanged
past value — the date of a close that already happened — passes, or every later Settings save
would fail). `update_settings` with `partial=True` keeps PATCH semantics for the API.

### 7. Where the fields live and what carries them
On the canonical survey only; readers go through `canonical_of()` (the gate already does for
embed hosts), and the Settings save routes to the canonical row. `SURVEY_COPY_EXCLUDED_FIELDS`
gains the three fields (Duplicate), the ZIP serializer does not write them (a backup restored
next year must not close on import), and the draft copy inherits nothing it needs
(`DraftCopyKeepsFieldsTest` covers sections and questions, not the header).

### 8. One module for the clock
`survey/schedule.py`: `due_for_close(now)` (the query), `phase(survey, now)` →
`'before' | 'open' | 'after' | None`, `format_in_zone(dt, tz)`, `next_event(survey)` for the
widget. The gate, the task, the widget and the API `out` all import it — no second definition of
"is it open".

## Risks / Trade-offs

- [Beat state file in an ephemeral container] → Beat recomputes from the static schedule on start;
  at most one five-minute slot is lost on a deploy. Acceptable for a close that the gate already
  enforces.
- [Worker down for hours] → Respondents still see the closed page (gate); creators see "Open" until
  the worker returns and the next run closes everything due in one pass. The management command is
  the manual remedy.
- [A wrong zone from the browser] → The panel shows the zone name next to the inputs and the widget
  echoes the resolved time; the API accepts an explicit offset.
- [Period edited while unpublished changes exist] → Settings on the draft copy save to the
  canonical row (same as embed hosts); publishing the draft never touches the period.
- [Held survey (content review) reaching `closes_at`] → Closed like any other; the review stays
  pending and `confirm_phishing` still finds its surveys.
- [Beat and `--concurrency 2`] → Beat is a thread in the main process, not a pool worker; the two
  pool processes keep serving AI generation and imports.

## Migration Plan

1. Migration adds three nullable columns; no data movement, safe in pre-deploy.
2. `render.yaml` worker command gains `-B`; the deploy restarts the worker with beat.
3. Rollback: revert the command (fields stay inert), or leave beat running with an empty schedule.
