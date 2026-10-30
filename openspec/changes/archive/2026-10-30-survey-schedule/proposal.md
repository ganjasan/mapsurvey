## Why

A paying customer asked for an end date so their survey stops taking answers on its own ("we're
closing our survey on Nov. 1"). Today closing is a manual status change, so someone has to remember
to do it on the day — often a weekend — or the owner does it for them by hand (issue #497). The
same customers plan a launch date too: the link goes into a newsletter or a council agenda days
before the consultation period starts. One **period** — "accepts answers from … to …" — covers both
ends with one mental model and one place in Settings.

## What Changes

- **A period on the survey**: optional `SurveyHeader.opens_at` and `closes_at` (UTC datetimes) plus
  `schedule_timezone` (the IANA zone the creator entered them in, for display only). Both ends are
  independent; `closes_at` must be after `opens_at`. The period lives on the canonical survey:
  unpublished changes, versions and the draft copy never carry their own.
- **Settings → "Survey period"**: two `datetime-local` inputs ("Opens on", "Closes on") in the
  survey's Settings panel, saved through `services.surveys.update_settings` (the existing autosave
  form), with the browser's zone recorded alongside. The publishing widget shows the next event
  ("Opens 3 Nov, 09:00" / "Closes 1 Nov, 23:59").
- **Respondent gate, exact to the minute**: `check_survey_access` reads the period on a `published`
  survey. Before `opens_at` respondents get a new "This survey opens on …" page (`200`, `noindex`,
  no session created); after `closes_at` they get the existing closed page immediately, without
  waiting for the job. Editors and owners bypass the gate as they do today.
- **Automatic close is a real close**: a periodic Celery task closes `published` surveys whose
  `closes_at` has passed through `services.publishing.transition(Actor(surface='schedule'), …,
  'closed')`, so the `AuditLog` row, the status and every creator surface are what a manual Close
  produces. Opening never changes status: the creator publishes by hand (content screening,
  translation-gap acknowledgement and the `survey_published` event stay human moments), and the
  gate holds the door until `opens_at`.
- **No instant re-close**: reopening a survey by hand (`closed → published`) clears a `closes_at`
  that is already in the past (audited), so the job cannot close it again; a future `closes_at` is
  kept, because the period still stands.
- **Celery beat**: the worker runs with an embedded beat (`-B`); the schedule task runs every five
  minutes and is also a management command for ops and previews.
- **REST and MCP**: `opens_at`, `closes_at`, `schedule_timezone` on `SurveyOut` and `SurveyPatchIn`
  (ISO 8601 with offset); `update_survey` picks them up through the shared schema. The generated API
  and MCP references are rebuilt.
- **Not in the ZIP, not copied**: the period is deployment-specific (a date, not structure); the
  backup file and *Duplicate* leave it behind, like `status` and `test_token`.
- Help centre how-to page, in-app "What's new" entry, creator strings in every offered catalog.

## Capabilities

### New Capabilities
- `survey-schedule`: the survey period — fields, Settings UI, the respondent gate before and after
  the period, the periodic close through the lifecycle service, the reopen rule, API/MCP exposure,
  and what copies/exports leave behind.

### Modified Capabilities
- `survey-access-control`: a `published` survey whose period has not started answers with the
  "opens on" page, and one whose period has ended answers with the closed page before the job runs.
- `rest-api-v1`: the survey resource carries the period fields; `PATCH /surveys/{uuid}` sets them
  with the same validation as Settings.

## Impact

- `survey/models.py` (+ migration), `survey/editor_forms.py::SurveyHeaderForm`,
  `survey/templates/editor/partials/survey_settings_panel.html`, `_publishing_widget.html`,
  `survey/access_control.py`, new `survey/templates/survey_not_yet_open.html`,
  `survey/services/publishing.py` (reopen rule), `survey/services/context.py` (`SURFACE_SCHEDULE`),
  `survey/schedule.py` (one module: due query, display helpers), `survey/tasks.py` + a management
  command, `mapsurvey/settings.py` (`CELERY_BEAT_SCHEDULE`), `render.yaml` and `docker-compose.yml`
  (worker command `-B`), `survey/cloning.py::SURVEY_COPY_EXCLUDED_FIELDS`.
- `api/v1/schemas.py`, `api/v1/forms_bridge.py`, `api/v1/out.py`, `help/src/content/docs/reference/
  api.md` and `mcp-tools.md` (generated), help how-to page, `survey/changelog/` entry, locale catalogs.
- Tests: `survey/tests/test_survey_schedule.py` (new capability module), deltas in
  `test_survey_access_control.py`, `api/tests/test_v1_*.py`.
- Operations: the Celery worker gains a beat loop; a second worker instance would need a
  dedicated beat process — noted in `render.yaml`.
