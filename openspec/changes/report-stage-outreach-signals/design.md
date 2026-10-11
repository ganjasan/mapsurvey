# Design — report-stage outreach signals

## Context

See proposal.md for motivation. What shapes the approach:

- Every fact but one is already in our rows: external, clean, non-empty sessions per survey
  (`SurveySession`, the `analytics.nonempty_sessions` gate, `EXCLUDED_VALIDATION_STATUSES`);
  the close as an `AuditLog(action='status_transition', metadata.new_status='closed')` row;
  geo features in `Answer`; the creator's segment in `UserCohort` and domain in `funnel.py`;
  `ProInterest` by user or email. The one missing fact is the creator's return to the data:
  `responses_viewed` / `data_exported` are emitted to PostHog in `analytics_views.py` and
  `views.py` and stored nowhere.
- `survey/content_screening.py` is the house pattern for "a weighted signal table, a pure
  `score()`, a threshold in settings, calibrated on known cases". The owner's manual outreach
  gives four known positives to calibrate against (the published customer stories).
- Staff tooling for creators exists: `CreatorProfile` + `CreatorNote` (append-only, `kind='signal'`
  already in the vocabulary, idempotent import by `source_path`), the funnel dashboard with two
  action lists, `export_creators` for GDPR, `send_templated_mail` to `CONTACT_EMAIL`.
- Scheduling on Render is a `cron` service on the same image running a shell script
  (`reclaim.sh`); the web service also has a token-gated `internal/` endpoint pattern for an
  external cron. There is no Celery beat.
- Rules this repo enforces: respondent data (`SurveySession`, `SurveyEvent`, `events.py`) never
  feeds creator analytics and vice versa; nothing names a customer in `openspec/`; the dashboard
  spec forbids new tables for stages derivable from existing rows.

## Goals / Non-Goals

**Goals:**
- One daily, deterministic, explainable decision per survey ("fired because: exported, closed").
- The export is the heaviest sub-signal, not a verdict: it still needs one more sign
  (a plateau, a close, repeated visits, or an institutional geo-rich survey) to fire.
- Zero creator- or respondent-visible change; zero new dependency; zero PostHog dependency at
  detection time.
- Calibration before trust: a dry run as of a past date over production data.

**Non-Goals:**
- Real-time alerts (a push on export). The owner acts once a day; the digest batches.
- Automating the materials archive or the story offer mail (next change).
- Any scoring of creators who have no survey in the eligible states.

## Decisions

### D1 — Two small tables, not reuse of `SurveyEvent` or `AuditLog`

`CreatorSurveyActivity(user FK, survey FK → canonical, kind, day DateField, count, last_at)`,
unique on `(user, survey, kind, day)`; `OutreachSignal(survey OneToOne → canonical, user FK,
score, signals JSON, status, note, fired_at, updated_at, worked_by FK null)`.

- `SurveyEvent` is the respondent system (CLAUDE.md boundary); a creator row there would be
  the exact confusion the analytics split exists to prevent.
- `AuditLog` is append-only and keyed by uuid without FK; counting "distinct days" out of it
  would mean parsing metadata per request. A day-grain row makes `revisited` one `COUNT(*)`.
- `OneToOne` on `survey` is the "fires once" rule as a constraint rather than a check in code;
  enrichment is an `UPDATE` of `signals`.

Rejected: a `signals` column on `SurveyHeader` (mixes outreach state into the product model,
exported in ZIPs, visible in the editor's queries).

### D2 — Persist at the emit site, through one helper

`product_events.record_return(kind, user, survey, **props)` does the upsert (`canonical_of(survey)`,
`F('count') + 1`, `update_or_create` under a try/except that logs) and then calls `emit()`.
The two call sites in `analytics_views.py` and `views.py::download_data` switch to it;
`views.py::export_survey` (the survey.json backup) keeps plain `emit()` — a backup is not a
return to the data. One helper means the spec scenario "the two can never disagree" is a
property of the code, not a test.

Rejected: a signal on PostHog capture (a vendor hook as the write path), and a middleware
matching URLs (fragile, and the view already knows the survey).

### D3 — Scoring is a pure function over a facts dataclass

`survey/report_stage.py`:

```
SUBSIGNALS = {  # name: (weight, window_days or None)
    'exported':      (4, 14),   # the heaviest: the report is being built now
    'closed':        (4, 14),
    'plateau':       (3, None),
    'revisited':     (3, 14),
    'geo_rich':      (2, None),
    'institutional': (2, None),
    'pro_interest':  (1, None),
}
MIN_RESPONSES = 30         # settings.REPORT_STAGE_MIN_RESPONSES
THRESHOLD = 7              # settings.REPORT_STAGE_THRESHOLD
PLATEAU_FRACTION = 0.2
PLATEAU_MIN_DAYS = 14
GEO_RICH_FEATURES = 50
```

`collect_facts(survey, as_of)` runs the queries (one aggregate per fact, canonical + versions
via `id = X OR canonical_survey_id = X`, the same session gate the Responses page uses) and
returns `SurveyFacts`; `score(facts)` has no DB and returns `(fires: bool, score: int,
signals: {name: value})`. With these weights `exported` (4) fires together with `plateau`
(3), `closed` (4) or `revisited` (3), or with `institutional` + `geo_rich` (2 + 2); alone it
does not. Exactly the `content_screening` split, so weights are a table and a
new sub-signal is a row plus one fact.

`plateau` = responses in the last 7 days `< PLATEAU_FRACTION ×` best 7-day window since
the first external session, and first session ≥ 14 days before `as_of`. Best window is
computed over daily counts (one `TruncDate` query), not calendar weeks, so a launch on a
Thursday is not split in two.

`as_of` is a parameter of every fact: `closed` reads audit rows `≤ as_of`, sessions are
filtered `start_datetime ≤ as_of`, return activity `day ≤ as_of`. That is what makes the
dry run retrospective.

### D4 — A management command on a Render cron, one run a day

`python manage.py detect_report_stage [--dry-run] [--as-of YYYY-MM-DD]`, run by a new
`cron` service `mapsurvey-report-stage` in `render.yaml` (same image, `plan: starter`,
`previews.generation: off`, schedule `0 6 * * *` UTC, `dockerCommand: sh ./report_stage.sh`
because Render's `dockerCommand` is not a shell — the recorded `reclaim.sh` lesson). It
needs `DATABASE_URL`, `SECRET_KEY`, the `EMAIL_*` block and `DEFAULT_FROM_EMAIL`, `SITE_URL`
and `POSTHOG_PROJECT_KEY`/`POSTHOG_API_HOST` (for the event; absent key = no event, as
everywhere).

Rejected: the token-gated `internal/` endpoint driven by an outside cron (scoring plus mail
inside a web request on the production worker; the purge endpoint exists because that job is
trivial). Rejected: Celery beat (there is none; adding a scheduler for one job).

The run is idempotent: `OneToOne` prevents a second firing, the dossier note is skipped by
`source_path`, the digest covers only rows created in this run. Running twice sends nothing
the second time.

### D5 — Deliveries

- **Dossier**: `CreatorNote(user=owner, author=None, kind='signal', happened_on=as_of,
  source_path=f'signal:report-stage:{survey.uuid}', body=…)`, skipped when the path exists.
  Body is a few markdown lines: survey name, response count, sub-signals, link to the signal.
- **Event**: `product_events.emit(OUTREACH_SIGNAL_FIRED, owner.pk, {survey_id, score,
  signals: [names]})` — ids only, consistent with every creator event.
- **Digest**: `send_templated_mail('survey/email/report_stage_digest', OUTREACH_SIGNAL_EMAIL,
  …)` with `OUTREACH_SIGNAL_EMAIL = env or CONTACT_EMAIL`. Links are absolute from `SITE_URL`:
  the signal's admin change page, the owner's admin user page (profile, cohorts and notes are
  inlines there), and `editor_survey_analytics` for the survey. No export link: a superuser
  can open Responses, and the archive the owner sends is the `survey-report` kit, not a raw
  download. The mail carries survey name, username, organisation, cohort, counts — never a
  respondent's answer.

### D6 — Eligibility and exclusions

Scored: `SurveyHeader` with `status in ('published', 'closed')`, `canonical_survey IS NULL`,
`deleted_at IS NULL`, `created_by` set, owner `is_staff=False, is_superuser=False` (the
`_real_users` population), not the `DEMO_SURVEY_URL` survey. Owner only — collaborators'
returns count as `exported`/`revisited` facts (they are the team building the report) but the
signal and the note belong to the owner, who is the account to write to.

### D7 — Dashboard panel reads the table

`CreatorFunnelService.report_stage_signals(limit=15)` returns open signals (`status in
('new', 'contacted')`, newest first) with the fields the template needs; the panel sits under
the two existing action lists and states "recorded since <first row's date>" per the
forward-only rule. No scoring happens in the request.

### D8 — Status workflow lives in the admin

`OutreachSignalAdmin`: list = survey, owner, score, sub-signals, status, fired_at;
`list_filter` on status; `list_editable` status; `readonly` everything but `status`/`note`;
links to the user page and the Responses page. "Won" is set by hand when a story or a Pro
sale follows — the conversion count of the outreach funnel comes from this column.

### D9 — The history is scored by walking each survey's timeline

`detect_report_stage --historical` evaluates every eligible survey (plus `archived` status
and already-worked creators, which the daily run also includes) at a sequence of `as_of`
dates: every 7th day from the first external session to today, then the exact day inside the
first firing week (a second pass at day grain over that week). The first `as_of` where
`score()` fires becomes `fired_at`; the record gets `historical=True`, `status='new'`, and
the dossier note is dated that day. Everything else is the daily code path — same
`collect_facts`, same `score()`, same `OneToOne` guard — so history and future cannot
diverge. No digest: the command prints one table (survey, owner, worked-since, fired day,
sub-signals, responses) and exits. Cost: ~300 surveys × ~20 dates × a handful of aggregate
queries, minutes, run by hand once.

Facts that history can and cannot supply: close dates exist in `AuditLog` since the audit
log shipped; before that a `closed` survey with no transition row is treated as closed on
`updated_at`, flagged in the summary. Return days before the backfill (D11) are empty,
which only lowers historical scores — never raises them.

### D10 — The "worked" checkbox lives on the dossier, the signal status on the survey

`CreatorProfile.outreach_done` (bool), `outreach_done_at` (date, null),
`outreach_outcome` (`''|no_reply|declined|story|pro`). The profile is the CRM-shaped row
(creator-dossiers D1), so a CRM import maps it to "Contact.last_contacted". Two levels on
purpose: a client is worked once; a signal is per survey and a known client's new survey is
a new signal, listed under "already in contact" in the digest and the panel.

Writes: (1) the checkbox in `UserAdmin.list_display` + `list_editable` through a profile
accessor that creates the profile row on first tick; (2) `OutreachSignalAdmin.save_model`
sets the flag when status becomes `contacted`/`won` and it is unset; (3)
`detect_report_stage --prefill-worked` marks creators with an `email` note by the earliest
note's date, never clearing or overwriting. `get_or_none` semantics everywhere: an absent
profile is "not worked".

Rejected: a boolean on `OutreachSignal` ("we handled this one") — it is what `status` already
says and it cannot answer "have we ever written to this person".

### D11 — Return activity before this change is restored from PostHog once

`backfill_creator_returns [--until YYYY-MM-DD]`: one HogQL query over `events` for
`responses_viewed` / `data_exported` with `timestamp_source = 'live'`, grouped by
`distinct_id` (= user pk), `properties.survey_id`, `toDate(timestamp)`; the request is the
`check_posthog_funnel_parity` pattern (`POSTHOG_PERSONAL_API_KEY` + `POSTHOG_PROJECT_ID`,
`/api/projects/<id>/query/`). Rows are inserted with `restored=True`,
`ignore_conflicts`, only for `day < until` where `until` defaults to the first day the
application recorded a row. Unknown user or survey → skipped and counted. Vendor failure
→ `CommandError`, nothing written. A `data_exported` with `format` absent is the survey
backup (`export_survey`) and is skipped — the forward helper records none either (D2).

## Risks / Trade-offs

- [False positives in the first weeks: `revisited`/`exported` are empty until the table fills,
  so only closes and plateaus fire] → the threshold needs `closed` (4) + `plateau` (3) or a
  `exported` + another; the digest shows the sub-signals, and `dismissed` is one click. Re-check the
  weights after 30 days of return rows.
- [Plateau on a survey that was never meant to collect much (a 35-response class exercise)]
  → the floor and the `institutional` weight; a wrong fire costs one digest line.
- [A survey with many versions re-published in one day looks "closed" never and "plateau"
  oddly] → versions are unioned; the close is read on the canonical row's transitions only.
- [Cron mail misconfiguration = silent no-digest] → the command logs the count it would mail
  and exits non-zero when the send raises; Render surfaces failed cron runs. Signals and notes
  are written before the send, so nothing is lost.
- [Rows about identifiable creators] → `export_creators` includes them; cascade on user
  delete; no respondent fact in either table.
- [Historical run fires on surveys whose moment passed a year ago] → that is the analysis the
  owner asked for: the list of missed clients. They sit in the panel as `new`, dated, and are
  worked or dismissed by hand; the digest never carries them.
- [The checkbox and the signal status disagree (client worked, signal `new`)] → by design:
  the flag says "we know this person", the status says "this survey's signal is open". The
  surfaces show both.
- [PostHog backfill double-counts a day the application also recorded] → `until` stops at the
  first recorded day and `ignore_conflicts` never touches an existing row.
- [Dashboard spec's no-new-table rule] → restated in the delta: forward-only creator facts
  with a stated start date, the same carve-out demo opens already have.

## Migration Plan

1. Migration adds the two tables (no data migration; no backfill).
2. Deploy web: return rows start accumulating immediately.
3. `backfill_creator_returns` once on production (needs the personal API key in the shell,
   never in `render.yaml`).
4. `detect_report_stage --prefill-worked`, then `--historical --dry-run`: the known outreach
   cases must appear with firing dates at or before the dates they were contacted; adjust
   weights/threshold in one commit if needed; then `--historical` for real.
5. Add the cron service in `render.yaml` (its first production run writes real signals).
6. Rollback: suspend the cron. Tables and the recording helper are harmless on their own.

## Open Questions

- Whether collaborators' return actions should also produce a dossier note on *their* timeline.
  Deferred: the owner is the outreach target; a note on the collaborator can be added later
  without changing the scoring.
