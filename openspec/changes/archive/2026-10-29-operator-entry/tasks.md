## 1. Model and migration

- [x] 1.1 Add `SurveySession.source` (`SOURCE_ONLINE` default, `paper`/`assisted`/`field`/`other`, choices + labels) and `entered_by` (FK `AUTH_USER_MODEL`, `SET_NULL`, `related_name='entered_sessions'`), with a short docstring tying `source` to "where the answers came from" vs `opened_by_kind`
- [x] 1.2 Add `audience` (`everyone`/`respondents`/`operators`, default `everyone`) to `SurveySection`, `QuestionGroup`, `Question`; constants and labels in `question_types.py` (`AUDIENCES`, `AUDIENCE_CHOICES`, `audience_allows(audience, surface)`)
- [x] 1.3 Migration `0109_operator_entry` (additive, defaults, no backfill); check `origin/master` for a parallel `0106` before committing

## 2. Visibility engine takes the surface

- [x] 2.1 `compute_visibility(survey, answers_by_code, enabled=None, surface='respondent')`: effective audience folded into `section_shown`, `group_visible`, `question_own`/`question_visible` as an AND term that the kill switch does not disable; same for `popup_visibility(parent, answers_by_code, enabled=None, surface=)`
- [x] 2.2 `_session_visibility`, `answers_by_code_for_session` callers in `views.py` pass `surface='respondent'`; `SurveySectionAnswerForm` takes `surface` and skips questions hidden for it (the POST purge already follows the map)
- [x] 2.3 `lint_rules`: warning "controller is not shown to respondents" when a controller's effective audience excludes respondents and the dependent's includes them; `describe_rule` surfaces it in the editor badge text
- [x] 2.4 Tests in `survey/tests/test_conditional_visibility.py` (delta: operator-only question discarded/purged on the respondent page, kill switch leaves audience on) and `survey/tests/test_question_audience.py` (cascade section→group→question, both surfaces, operator-only controller)

## 3. Extract the section save (no behaviour change)

- [x] 3.1 Move the POST body of `survey_section` (answer purge, per-type storage, object answers, final visibility) into `save_section_answers(post, session, session_survey, section, surface)` in `survey/views.py` returning the final `VisibilityMap`; `survey_section` calls it then does events, shared-map sync and redirects exactly as before
- [x] 3.2 Run `survey.tests.test_answer_persistence survey.tests.test_conditional_visibility survey.tests.test_object_answers survey.tests.test_geo_multi_feature_input survey.tests.test_spraycan_question survey.tests.test_file_upload_questions survey.tests.test_shared_map_layer` green (commit only on the owner's word)

## 4. Operator sessions have no side effects

- [x] 4.1 `signals.py`: `survey_first_response` skips `source != online` and excludes such sessions from the "already answered" check; `record_demo_open` not called on the entry path
- [x] 4.2 `layers.sync_question_layers_for_session` and `backfill_question_layer` skip sessions with `source != online`
- [x] 4.3 Tests: `test_creator_funnel_events.py` (entered sheets do not count or suppress), `test_shared_map_layer.py` (entered point off the layer, backfill skips), `test_survey_performance_analytics.py` (funnel unchanged after entries; no `SurveyEvent` rows)

## 5. Pro feature

- [x] 5.1 `billing/features.py`: `operator_entry` for `pro` with label; `billing/tests/test_plan_entitlements.py` delta
- [x] 5.2 Settings/`.env` nothing new; confirm `require_feature` works with an `org_getter` that resolves the survey's organisation from `survey_uuid`

## 6. Entry surface

- [x] 6.1 `survey/operator_entry_views.py`: `entry_header` (GET/POST; `survey_permission_required('editor')` + `require_feature('operator_entry')`; `EntryHeaderForm` with source, version from `family_headers`, language; POST creates the session with `source`, `language`, `entered_by`, `opened_by_kind=session_kind_for`), `entry_section` (GET/POST; session lookup = family + `source != online` + role, 404 otherwise; `_build_section_context(..., entry=True)` with `surface='operator'`; POST → `save_section_answers` → next visible section or `entry_saved`), `entry_saved` (sets `mark_completed`, renders Saved with *Next sheet* carrying `?source=&version=&language=` and *Back to Responses*), `entry_cancel`
- [x] 6.2 URLs under `editor/surveys/<uuid>/responses/enter/…` (names `operator_entry_header`, `operator_entry_section`, `operator_entry_saved`); add the view names to `POSTHOG_EXCLUDED_VIEW_NAMES`
- [x] 6.3 Templates `editor/operator_entry/header.html`, `section.html` (extends the respondent base in entry mode: reuse `partials/survey_section_partial.html` and the map/draw scripts; `entry` flag hides language picker, abuse footer, embed carrier, "Made with" badge; the progress line reads "Sheet · section N of M"), `saved.html`; HTMX navigation posts to the entry URLs
- [x] 6.4 `SurveySectionAnswerForm(surface='operator')`: respondent-facing fields `required=False`, operator-only keep their own; `_get_form_from_input_type` unchanged otherwise
- [x] 6.5 Responses toolbar (`analytics_dashboard_v2.html`, `_survey_more_menu.html` if that is where Export sits): *Enter a response* for editors, locked + billing link without the feature (`{% has_feature %}`), hidden for viewers
- [x] 6.6 Tests `survey/tests/test_operator_entry.py`: role and feature gates (editor Pro / viewer / Free / lapsed keeps sessions / closed survey), header validation and session creation on an archived version, foreign and online session ids 404, respondent cookie untouched, answers stored, visibility applies, soft required (attribute present only on operator-only fields), finish sets `end_datetime`, next sheet prefills, abandoned entry is an empty session

## 7. Read surfaces

- [x] 7.1 `SurveyAnalyticsService.get_table_page`: `source` system column after Status (v2 and legacy), values filter through `col_filters`, unique values for the filter sheet; drawer (`analytics_session_detail.html`) shows source label + `entered_by` username
- [x] 7.2 `export.py`: `SESSION_COLUMNS` + `sessions_rows` gain `source`, `entered_by`; `serialization.py` responses file writes/reads `source` (missing = `online`) and `entered_by`
- [x] 7.3 Tests: `test_operator_entry.py` (filter paper only, drawer, overview counts them), `test_response_data_export.py` (sessions sheet columns), `test_survey_serialization.py` (responses file round trip, old file reads online)

## 8. Editor: audience control, structural rule, travel

- [x] 8.1 `editor_forms.py`: `audience` on `SurveySectionForm`, `QuestionGroupForm`, `QuestionForm`; services pass it through (the forms bind it; `partial=True` semantics unchanged)
- [x] 8.2 `versioning.py`: `question_snapshot`/`section_snapshot` and the group equivalent include `audience`; `structural_*_changes` add "the audience"; `test_live_survey_editing.py` delta (live refused with the reason, draft accepted, publish carries it)
- [x] 8.3 `_visibility_block.html` + `_visibility_block_context`: "Who sees this" audience select beside the rule for section, group, question and sub-question hosts; badges "Operators only" / "Respondents only" in `section_list_item.html`, `group_list_item.html`, `question_list_item.html`
- [x] 8.4 `serialization.py` structure export/import: `audience` on sections, groups, sub-question groups, questions, sub-questions; unknown value → warning line + `everyone`; `test_survey_serialization.py` delta
- [x] 8.5 `DraftCopyKeepsFieldsTest` and `test_question_groups.py` duplicate/paste assertions cover `audience` (plain field — expect no code change); translation table lists operator items (assert in `test_translation_table.py`)
- [x] 8.6 AI generation writes no audience: assert in `test_ai_survey_generation.py` that generated items are `everyone`

## 9. API and MCP

- [x] 9.1 `api/v1/schemas.py`: `audience: Literal[...]` optional on `SectionIn`/`GroupIn`/`QuestionIn` (and their PATCH variants), present on the `Out` models; `forms_bridge.py` passes it; `out.py` returns it; MCP tools inherit through `args_model`
- [x] 9.2 Regenerate `help/src/content/docs/reference/api.md` and `reference/mcp-tools.md` (`scripts/build_api_reference.py`, `scripts/build_mcp_reference.py`)
- [x] 9.3 `api/tests/test_v1_live.py` delta: PATCH sets and GET returns, unknown value 422, live survey 409

## 10. i18n, help, changelog

- [x] 10.1 New creator strings (header labels, source labels, audience labels, badges, toolbar, Saved page) appended by hand to every offered catalog; `TranslationCatalogHygieneTest` green
- [x] 10.2 Help page `help/src/content/docs/how-to/enter-responses-for-others.md` (paper sheets, assisted interviews, operator-only questions, where the source shows up, Pro); `survey/help_links.py` key `operator_entry` linked from the header page; `HelpSiteLinksTest` green
- [x] 10.3 No changelog entry in this PR (owner, 2026-10-29): one "What's new" card covers the whole epic #350 and ships with a later PR of the epic

## 11. Verification

- [x] 11.1 `SpecTestLineageTest`: `operator-entry` and `question-audience` sit in `UNMAPPED_MODULES` ("spec lives in the unarchived change operator-entry") until archive; the archive commit removes both entries (the stale-entry test enforces it)
- [x] 11.2 Full run `./run_tests.sh survey billing api mcp newsletter` green; `openspec validate operator-entry --strict`
- [x] 11.3 `/verify` on this worktree's dev server: enter one sheet on an archived version of a two-version survey with an operator-only section; check Responses (column, filter, drawer), the workbook export, the Perf pane unchanged, the respondent page without the operator section
