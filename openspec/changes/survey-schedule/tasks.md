## 1. Model and the clock module

- [x] 1.1 Add `opens_at`, `closes_at` (nullable `DateTimeField`, indexed `closes_at`) and `schedule_timezone` (`CharField(64, blank)`) to `SurveyHeader`; migration
- [x] 1.2 `survey/schedule.py`: `phase(survey, now)`, `due_for_close(now)` queryset (canonical, not deleted, published, `closes_at <= now`), `format_in_zone()`, `next_event(survey, now)`
- [x] 1.3 `SURVEY_COPY_EXCLUDED_FIELDS` gains the three fields; `serialization.py` leaves them out of `survey.json` on export and ignores them on import

## 2. Service layer

- [x] 2.1 `services/context.py`: `SURFACE_SCHEDULE = 'schedule'`
- [x] 2.2 `SurveyHeaderForm`: the three fields, `datetime-local` widgets, `clean()` — naive values read in `schedule_timezone`, `closes_at > opens_at`, a changed `closes_at` must be in the future; zone validated against `zoneinfo.available_timezones()`
- [x] 2.3 `services.surveys.update_settings`: period fields are written on `canonical_of(survey)` (same routing as embed hosts), PATCH semantics under `partial=True`
- [x] 2.4 `services.publishing.transition`: on `closed → published` clear a past `closes_at` (and a past `opens_at`), audit `schedule_cleared`; the task passes `scheduled=True` into the `status_transition` audit metadata

## 3. Respondent gate

- [x] 3.1 `survey_not_yet_open.html` (extends `base_survey_template`/`base.html` like `survey_closed.html`): name, opening time in the survey's zone, no session
- [x] 3.2 `check_survey_access`: after the held check on `published`, `phase()` → before: render the page `200` + `request.survey_noindex = True`; after: `survey_closed.html`
- [x] 3.3 Confirm the section POST path goes through the gate (no answers stored after `closes_at`)

## 4. Periodic task and operations

- [x] 4.1 `survey/tasks.py::apply_survey_schedule` (shared task): iterate `due_for_close` with `select_for_update(skip_locked=True)`, one transaction per survey, `transition(Actor(None, surface='schedule'), …, 'closed')`, log and continue on failure, return the count
- [x] 4.2 Management command `apply_survey_schedule` calling the same function
- [x] 4.3 `settings.py`: `CELERY_BEAT_SCHEDULE` (every 5 minutes), `CELERY_TIMEZONE='UTC'`
- [x] 4.4 `render.yaml` worker and `docker-compose.yml` celery: `worker -B -s /tmp/celerybeat-schedule`, with the "one instance only" comment

## 5. Editor UI

- [x] 5.1 Settings panel: "Survey period" block — two inputs, hidden `schedule_timezone` filled from `Intl.DateTimeFormat().resolvedOptions().timeZone`, zone shown, help text, "Learn more" via `HELP_URL.survey_period`
- [x] 5.2 Publishing widget: next event line under the status chip (`next_event`), on the full settings page and the panel twin
- [x] 5.3 Initial values rendered in the survey's zone for `datetime-local` (`value="YYYY-MM-DDTHH:MM"`)

## 6. REST and MCP

- [x] 6.1 `schemas.py`: `SurveyOut` + `SurveyPatchIn` fields; `forms_bridge.survey_settings` maps them (ISO strings pass through, `None` → empty string clears); `out.survey` emits them in UTC
- [x] 6.2 MCP `update_survey` description names the period; regenerate `help/src/content/docs/reference/api.md` and `mcp-tools.md`

## 7. Help, changelog, i18n

- [x] 7.1 `help/src/content/docs/how-to/set-a-survey-period.md` + `help_links.py` key `survey_period`
- [x] 7.2 `survey/changelog/2026-10-30-survey-period.html` (kind: new)
- [x] 7.3 New creator strings appended to every offered locale catalog (`TranslationCatalogHygieneTest`), `.mo` compiled

## 8. Tests

- [x] 8.1 `survey/tests/test_survey_schedule.py`: form validation (order, changed past, unchanged past), canonical routing, gate before/after/held/testing/editor bypass, no session on the "opens on" page, task closes due + skips others + survives a failure, management command, reopen clears past / keeps future, duplicate and ZIP leave the period behind, widget text
- [x] 8.2 `survey/tests/test_survey_access_control.py`: the four delta scenarios
- [x] 8.3 `api/tests/test_v1_*.py`: read/set/clear/422/draft-uuid routing; `mcp/tests/test_reference.py` stays green after regeneration
- [x] 8.4 Run `./run_tests.sh survey.tests.test_survey_schedule survey.tests.test_survey_access_control survey.tests.test_survey_service_layer survey.tests.test_test_suite api mcp`, then the full set once

## 9. Verification

- [x] 9.1 `openspec validate survey-schedule --strict`
- [x] 9.2 Dev server: set a period in Settings, open the respondent URL in a private window before/after, run the management command, reopen, confirm no re-close
