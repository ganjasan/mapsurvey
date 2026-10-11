# Tasks — report-stage outreach signals

## 1. Models + migration

- [ ] `CreatorSurveyActivity` in `survey/models.py`: `user` FK (CASCADE,
      `related_name='survey_returns'`), `survey` FK → canonical `SurveyHeader` (CASCADE,
      `related_name='creator_returns'`), `kind` (`responses_viewed` | `data_exported`),
      `day` DateField, `count` PositiveIntegerField, `last_at` DateTimeField; unique
      `(user, survey, kind, day)`; index `(survey, kind, day)`.
- [ ] `OutreachSignal`: `survey` OneToOne → canonical (CASCADE, `related_name='outreach_signal'`),
      `user` FK (CASCADE), `score` int, `signals` JSONField (`{name: value}`), `status`
      (`new|contacted|dismissed|won`, default `new`, db_index), `note` TextField blank,
      `fired_at` (default now), `updated_at` (auto_now), `worked_by` FK null SET_NULL.
      `Meta.ordering = ('-fired_at',)`.
- [ ] Schema migration.

## 2. Recording creator returns (`creator-return-activity`)

- [ ] `product_events.record_return(kind, user, survey, **props)`: upsert the day row for
      `canonical_of(survey)` (`update_or_create` + `F('count')+1`, `last_at=now`) inside
      try/except that logs; then `emit(kind, user.pk, {'survey_id': …, **props})`.
      Constant `OUTREACH_SIGNAL_FIRED = 'outreach_signal_fired'`.
- [ ] `analytics_views.py:118` → `record_return(RESPONSES_VIEWED, …)`.
- [ ] `views.py::download_data` (line ~1538) → `record_return(DATA_EXPORTED, …, format=fmt)`;
      `export_survey` (line ~1601) keeps plain `emit`.
- [ ] `export_creators`: include the user's return rows (kind, survey uuid, day, count) next to
      the notes.
- [ ] Admin: read-only `CreatorSurveyActivity` list (user, survey, kind, day, count), filters
      on kind/day, search on username.
- [ ] Tests (`CreatorReturnActivityTest`): first visit creates count 1; second visit same day
      → count 2, one row; archived-version download records the canonical survey; rejected
      format records nothing; `export_survey` records nothing; a forced DB error still serves
      the page; PostHog disabled still records.

## 3. Scoring (`survey/report_stage.py`)

- [ ] `SUBSIGNALS`, `HARD_TRIGGERS`, `MIN_RESPONSES`, `THRESHOLD`, `PLATEAU_FRACTION`,
      `PLATEAU_MIN_DAYS`, `GEO_RICH_FEATURES` at the top; threshold and floor read from
      `settings.REPORT_STAGE_THRESHOLD` / `REPORT_STAGE_MIN_RESPONSES` with those defaults.
- [ ] `SurveyFacts` dataclass: `responses`, `daily_counts`, `first_session_at`, `closed_at`,
      `export_days`, `view_days`, `geo_features`, `segment`, `institutional_domain`,
      `pro_interest`.
- [ ] `collect_facts(survey, as_of)`: canonical + versions (`Q(id=…) | Q(canonical_survey_id=…)`),
      sessions `opened_by_kind='external'`, `is_deleted=False`, validation status not in
      `EXCLUDED_VALIDATION_STATUSES`, non-empty (`analytics.nonempty_sessions`),
      `start_datetime <= as_of`; daily counts via `TruncDate`; `closed_at` from the latest
      `AuditLog(action='status_transition', survey_uuid=…, metadata.new_status='closed',
      created_at <= as_of)`; return days from `CreatorSurveyActivity` (any user, `day <= as_of`);
      geo features = count of `Answer` rows with a geometry (`question_types.GEO_TYPES`) in
      those sessions; segment from `UserCohort` (dimension `segment`), domain via
      `funnel._domain` + `FREEMAIL_DOMAINS`; `pro_interest` by `user` or `email`.
- [ ] `score(facts, as_of) -> ScoreResult(fires, score, signals)`: pure; `plateau` = last 7 days
      < fraction × best 7-day window since first session, and first session ≥ 14 days before
      `as_of`; hard trigger rule; threshold rule; profile sub-signals alone never fire.
- [ ] `eligible_surveys(as_of)`: published/closed, canonical, not trashed, owner real
      (non-staff), not the demo survey.
- [ ] Tests (`ReportStageScoringTest`, pure `score()` over hand-built facts): below floor;
      export alone fires; `institutional`+`geo_rich` alone does not; plateau present/absent;
      closed outside window; profile-only never fires; `as_of` shifts every window.

## 4. The run (`detect_report_stage`)

- [ ] `survey/report_stage.py::run(as_of=None, dry_run=False) -> RunReport` loops eligible
      surveys; per survey try/except → log and continue; for each firing with no existing
      `OutreachSignal`: create the record, write the `CreatorNote` (kind `signal`,
      `source_path='signal:report-stage:<uuid>'`, skip if exists), emit the event; for an
      existing record: merge new sub-signals into `signals`, never change status, not in digest.
- [ ] Digest: `send_templated_mail('survey/email/report_stage_digest', settings.OUTREACH_SIGNAL_EMAIL, …)`
      only when the run fired ≥ 1; `.txt` + `.html` templates listing survey, owner
      (username, `CreatorProfile.organization`, segment cohort), response count, sub-signals
      with values, links (`SITE_URL` + admin change url of the signal, admin user page,
      `editor_survey_analytics`). Signals/notes/events are written before the send; a send
      error is logged and the command exits non-zero.
- [ ] Management command `detect_report_stage` with `--dry-run` (prints would-fire rows with
      sub-signals, writes nothing, sends nothing) and `--as-of YYYY-MM-DD`.
- [ ] Settings: `OUTREACH_SIGNAL_EMAIL = env or CONTACT_EMAIL`, `REPORT_STAGE_THRESHOLD`,
      `REPORT_STAGE_MIN_RESPONSES`.
- [ ] Tests (`ReportStageRunTest`): fires once and enriches on the second run; re-run same day
      creates/sends nothing; two firings → one mail with two entries, two notes, two events
      (patch `emit`); dismissed signal gains sub-signals and keeps status; one survey raising
      does not stop the others; dry-run writes nothing; mail failure leaves the records;
      staff-owned and demo surveys skipped; collaborator export counts as `exported`.

## 5. Staff surfaces

- [ ] `OutreachSignalAdmin`: list (survey, owner, score, sub-signal names, status, fired_at),
      `list_filter=('status',)`, `list_editable=('status',)`, readonly facts, `note` editable,
      links to the owner's user page and the Responses page; `worked_by` set to the editing
      staff user on save.
- [ ] `CreatorFunnelService.report_stage_signals(limit=15)` + "Report stage" panel in
      `templates/admin/funnel_dashboard.html` under the two action lists, with the
      "recorded since <date>" line; test that `new`/`contacted` show and `dismissed`/`won` do not.

## 6. Deployment

- [ ] `report_stage.sh` (`set -e; python manage.py detect_report_stage`) and the
      `mapsurvey-report-stage` cron service in `render.yaml` (starter, previews off,
      `0 6 * * *`, `DATABASE_URL`, `SECRET_KEY`, `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `SITE_URL`,
      `POSTHOG_PROJECT_KEY`, `POSTHOG_API_HOST`, `OUTREACH_SIGNAL_EMAIL` sync off).
- [ ] Calibration note in the change: run `--dry-run --as-of` for the known cases on
      production before enabling the cron; record the outcome (pseudonymised) in the ops repo.

## 7. Docs

- [ ] `CLAUDE.md`: a "Report-stage outreach signals" paragraph (tables, the one helper,
      the weights table rule, the cron, what the digest may contain).
- [ ] `openspec/changes/report-stage-outreach-signals`: keep `RepoHygieneTest` clean — no
      names, no emails.
