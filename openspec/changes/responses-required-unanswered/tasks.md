## 1. Stored state and the one function

- [x] 1.1 Migration `0131`: `SurveySession.required_missing` (JSONField, default list) and `required_complete` (BooleanField, default True so it agrees with the empty list, db_index)
- [x] 1.2 `survey/required_state.py`: `missing_required(session, vmap=None, answers=None)` per design D2 (surface by `is_operator_entry`, visibility engine, `html`/`image` excluded, value-carrying rows, `min_features`, `min_objects`)
- [x] 1.3 `refresh(session, vmap=None)` and `refresh_many(qs)` (grouped by header, structure loaded once, answers per chunk of 500, empty sessions skipped)
- [x] 1.4 Celery task `recompute_required_state(header_id)` with synchronous fallback when enqueue fails
- [x] 1.5 Tests for the rules: later page never reached, optional last page, question rule, section rule, group rule, audience (operator-only on paper vs online), geo minimum, objects minimum, blank inline row, no required questions

## 2. Triggers

- [x] 2.1 End of `views.save_section_answers` (after object answers), reusing `vmap_final`; covers respondent, operator entry, paper entry, forward and Back
- [x] 2.2 `analytics_answer_edit`
- [x] 2.3 `paper/review.py::supersede_machine_answers`
- [x] 2.4 `serialization.import_responses_from_archive` (imported sessions)
- [x] 2.5 `services/questions.py`: on update when `required`, `min_features` or `min_objects` changes, and on delete of a question with answers → `transaction.on_commit` recompute of the header
- [ ] 2.6 Data migration `0132` backfilling non-empty sessions via `refresh_many`; time it on a production-sized local copy and note the runtime in the PR — migration written; timing NOT done (production DB unreachable from this machine on 2026-11-16)
- [x] 2.7 Tests for each trigger, including ticking Required on a published survey with responses, and publish leaving old sessions' state unchanged (import and paper-supersede triggers are wired but have no dedicated test)

## 3. One completion definition everywhere

- [x] 3.1 `analytics.completed_session_filter(qs)` = `nonempty_sessions(qs).filter(required_complete=True)`; drop the `headers` argument and update callers (`analytics.py`, `export.py`, `api/v1/responses.py`)
- [x] 3.2 `family_completion_counts` (dashboard cards) reads `required_complete`; remove its inline last-section rule
- [x] 3.3 `get_hourly_sessions` / `get_daily_sessions` / `get_session_hours` read `required_complete`; remove `_last_section_ids` and last-section completion helpers that become unused
- [x] 3.4 `completed_only` descriptions in `api/v1/schemas.py` and `mcp/tools/responses.py` → "Only responses that answered every required question."; regenerate `reference/api.md` and `reference/mcp-tools.md`
- [x] 3.5 Agreement test: Overview completed = Complete chip = `completed_only` export rows = API summary `completed` on one fixture

## 4. Remove Issues and per-answer lints (server)

- [x] 4.1 Delete `compute_session_issues` and its rules; `get_overview` drops `flagged_count`; `get_overview_extras` drops `needs_review` and per-item `issues`
- [x] 4.2 Replace `compute_answer_lints` with `crossed_shapes(...)` (self-intersection only); delete `_WARNING_TYPES` / `_ERROR_TYPES`, `anomaly_counts`, `v2_counts['issues']`
- [x] 4.3 `get_table_page`: system column `issues` → `required` (names from the session header by code, sorted by count, in the search haystack); filter `required=missing` / `complete`; ignore `issues=`
- [x] 4.4 `analytics_views.analytics_table` passes the new filter; delete `analytics_validation_settings` view and URL
- [x] 4.5 `parse_validation_settings`: drop `outlier_sigma`, `min_length`, `area_outlier_factor`; remove them from `ValidationSettingsIn` and `forms_bridge.VS_KEYS`
- [x] 4.6 `templatetags/survey_filters.py`: `lint_tooltip` keeps only the crossed-shape text

## 5. Remove Issues (templates, JS, CSS)

- [x] 5.1 `_analytics_table_engine.html`: delete `_ANOMALY_*`, sidebar machinery, `selectAllFlagged`, validation-settings JS; `issues` param → `required`
- [x] 5.2 `analytics_table.html`: chips All / Complete / Required unanswered / Trash (desktop and phone toolbar), delete `#anomaly-counts-data`, `#active-issues-filter`, legacy Issues select and pills, validation cog; Issues cell → quiet marker with tooltip; lint cell → crossed-shape mark only, neutral style
- [x] 5.3 `analytics_dashboard_v2.html`: delete `#validationSettingsModal`, `rv2IssuesMenu`, Responses-tab badge; phone filter sheet loses Violations, gains the two options
- [x] 5.4 `analytics_dashboard.html` (legacy): delete anomalies strip/sidebar and validation modal
- [x] 5.5 `analytics_overview_pane.html` / `analytics_overview.html`: delete flagged tile and Needs-review block; latest feed shows validation status only
- [x] 5.6 `responses-v2.css`: delete `.rv2-issues-*`, `.rv2-kpi.rv2-flag`; add the neutral marker style
- [x] 5.7 Bulk trash / permanent delete: in-page delete modal stating the count, replacing `confirm()`
- [x] 5.8 Question modal: remove outlier sigma, min length, area factor inputs; Min/Max shown for number only
- [x] 5.9 New creator strings appended to every offered locale catalog (`TranslationCatalogHygieneTest`)

## 6. Number Min/Max for respondents

- [x] 6.1 `SurveySectionAnswerForm`: number input gets `min` / `max` from `validation_settings`
- [x] 6.2 `save_section_answers`: drop a number value outside the bounds
- [x] 6.3 Tests: rendered attributes, tampered POST not stored, no bounds = any value

## 7. Tests, docs, changelog

- [x] 7.1 New module `survey/tests/test_responses_required_unanswered.py` (marker tooltip, filter, removed signals, bulk modal text) and `test_number_question_bounds.py`; register both specs' lineage
- [x] 7.2 Delete tests of removed behaviour and update tests of changed definitions (`test_response_validation_management`, `test_responses_empty_sessions`, `test_analytics_data_workspace`, `test_responses_navigation`, `test_responses_overview`, `test_survey_analytics_basic`, `test_cross_version_analytics`, `test_survey_editor`, `test_responses_export_formats`, `test_survey_service_layer`, `test_draft_copy_lifecycle`, `api/tests/test_v1_responses`)
- [x] 7.3 Help: `start-here/read-and-export.md`, `how-to/export-responses.md`, `reference/exports.md` — new meaning of completed, no "flagged"
- [x] 7.4 What's new entry `survey/changelog/2026-11-<dd>-responses-required.html` (corner card): Issues gone and why, completed = every required question answered, Min/Max now enforced, trashed responses can be restored
- [x] 7.5 CLAUDE.md: replace the `completed_session_filter` / "answered the last section" notes and the empty-sessions paragraph's issue references with the new definition
- [x] 7.6 Full suite `./run_tests.sh survey billing api mcp newsletter` green; `openspec validate --strict`
