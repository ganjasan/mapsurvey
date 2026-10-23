# PR 1 — service layer (editor only, no API)

## 1. Baseline and scaffolding

- [x] 1.1 Baseline run: `./run_tests.sh survey` and `./run_tests.sh survey.test_question_groups` on the untouched branch; record pass/fail counts in the PR notes
- [x] 1.2 Create `survey/services/` with `__init__.py`, `context.py` (`Actor`, `Actor.from_request`), `errors.py` (`ServiceError` and the D3 subclasses)
- [x] 1.3 `survey/audit.py`: add `record(actor, action, survey=None, **metadata)`; `audit(request, …)` delegates to it; test both swallow exceptions (GIVEN/WHEN/THEN)

## 2. Shared rules moved out of the views

- [x] 2.1 Move `_edit_locks`, `_check_content_edit_allowed`, `_check_not_shadowed_by_draft`, `_rescreen_if_live` logic into `services/locks.py` (`locks(survey)`, `assert_content_editable`, `assert_structure_editable`, `rescreen_if_live`); editor helpers become thin wrappers returning today's responses
- [x] 2.2 Move `_guard_choice_codes` into `services/questions.py` (`guard_choice_codes`); parse choices JSON with `ValidationFailed` instead of an unguarded `json.loads`
- [x] 2.3 Move `_save_section_translations` / `_save_question_translations` into the services taking a `{lang: {field: value}}` dict; the editor builds that dict from POST
- [x] 2.4 `questions.parse_validation_settings(input_type, data)` — one parser from the edit view's inline code + `_parse_file_validation_settings`; tests per type incl. min > max refusal
- [x] 2.5 `visibility.validate_rule(kind, host, rule)` (strict, pure) + the shape parse moved from `_parse_visibility_rule` into the service (`strict` flag); unit tests for later controller, wrong type, unknown choice code, sub-question in another pop-up

## 3. Survey services

- [x] 3.1 `services/surveys.py::create_blank(actor, organization, name, language, map_start, …)` from `_finish_blank_survey` (collaborator owner, head section, `survey_created` event); `editor_survey_create` and `editor_survey_create_blank` call it
- [x] 3.2 `update_settings(actor, survey, data, files)` over `SurveyHeaderForm` (+ `_check_not_shadowed_by_draft`, `rescreen_if_live`); settings page and settings panel call it
- [x] 3.3 `rename`, `set_thanks(actor, survey, html_by_lang, show_results)`, `set_map_position(actor, survey, lat, lng, zoom, use_geolocation)` (ValidationFailed on non-numbers) — views switched
- [x] 3.4 `trash(actor, survey)` wrapping `trash.trash_survey` + audit; `delete_survey` view calls it
- [x] 3.5 Run the Create / Settings / Audit-trash test groups from the extraction map

## 4. Section services

- [x] 4.1 `services/sections.py::create(actor, survey)` (linked-list append, head on first) — `editor_section_create` switched
- [x] 4.2 `update(actor, section, data, translations, visibility, strict=False)`: form + rule validated BEFORE any write; structural classification with `StructureLocked`; `live_edit_saved` + rescreen — `editor_section_detail` switched
- [x] 4.3 `delete(actor, section, acknowledge_answer_loss)` with `AnswersAtRisk` — `editor_section_delete` switched
- [x] 4.4 `reorder(actor, survey, section_ids)`: refuses unknown/foreign/non-int ids with `ValidationFailed` (editor → 400) — `editor_sections_reorder` switched; test for the former 500
- [x] 4.5 `set_map(actor, section, …)` — `editor_section_map_picker` switched
- [x] 4.6 Run Sections test groups + `ReadOnlyLockTest`, `LiveSurveyEditingTest`

## 5. Question services

- [x] 5.1 `services/questions.py::create(actor, section, data, files, *, parent=None, group_id=None, draft_on_type_pick=False, translations, visibility, strict=False)` — layer choice resolved AFTER validation; `editor_question_create` (both draft and full paths) and `editor_subquestion_create` switched
- [x] 5.2 `update(actor, question, data, files, translations, visibility, strict=False)` incl. shared-map settings and structural classification — `editor_question_edit` (incl. autosave 422) switched
- [x] 5.3 `set_choices(actor, question, choices)` (guard + extras + clamp, structural check for removed answered codes)
- [x] 5.4 `delete(actor, question, acknowledge_answer_loss, if_empty=False)` with `DeleteBlocked` / `AnswersAtRisk` — `editor_question_delete` switched
- [x] 5.5 `reorder(actor, section, parent, items)` from `_apply_nested_order` (group-aware) — `editor_items_reorder` switched; legacy `editor_questions_reorder` calls a flat variant with int-guarding
- [x] 5.6 `set_share(actor, question, value)` — `editor_question_share` switched
- [x] 5.7 Run Questions + Groups/move test groups

## 6. Lifecycle services

- [x] 6.1 `services/publishing.py::transition(actor, survey, status, acknowledge_translation_gaps, clear_test_data)` returning `{status, review}` — `editor_survey_transition` switched (audit-before-save order kept)
- [x] 6.2 `create_draft(actor, survey)`, `restore_version(actor, survey, version)`, `publish_draft(actor, draft, force, acknowledge_translation_gaps)`, `discard_draft(actor, draft)` — the four views switched
- [x] 6.3 Run Lifecycle/versioning + `ContentScreeningFlowTest` + `DraftCopyKeepsFieldsTest`

## 7. Service-level tests and PR 1 close

- [x] 7.1 `survey/tests/test_services_*.py` (or classes in `survey/tests.py` per repo convention): one class per service module — atomic rollback, validate-before-write, `Actor` in audit, same-bytes editor vs service for subtext and thanks
- [x] 7.2 Full `./run_tests.sh survey` + `test_question_groups` + `./run_e2e.sh` for section/question CRUD, lifecycle, creation; compare to 1.1
- [x] 7.3 `CLAUDE.md`: "Service layer" paragraph (one write path, Actor, forms as validators, errors); PR 1 opened with the extraction map and the 500→400 note

# PR 2 — REST API v1

## 8. Framework and cross-cutting

- [x] 8.1 `pipenv install "django-ninja~=1.7"`; lock; venv reinstalled
- [x] 8.2 `api/v1/__init__.py` NinjaAPI (`urls_namespace='api_v1'`, csrf off, docs page off), mounted at `/api/v1/`; `/api/v1/openapi.json` public
- [x] 8.3 `api/v1/auth.py` BearerAuth over `api.auth.authenticate(request,'api')` + `limits.check_request`; `@scoped(...)` checks scopes before body parsing
- [x] 8.4 `api/v1/errors.py` handlers: `ApiError` → envelope; `ServiceError` → D3 table; ninja/pydantic `ValidationError` → `422 validation` + `fields`; unknown route → `404 not_found`; `Exception` → `500 server_error` + PostHog capture without the bearer; add `forbidden_role`, `validation`, `draft_required`, `answers_at_risk`, `delete_blocked`, `translation_gaps`, `incompatible_draft`, `conflict`, `bad_cursor`, `transition_refused` to `api/errors.py`
- [x] 8.5 `api.middleware.ApiResponseHeadersMiddleware`: `Cache-Control: no-store`, CORS `*` without credentials, `OPTIONS` preflight `204` for `/api/`
- [x] 8.6 `api/v1/pagination.py` signed cursor bound to its list, limit clamp
- [x] 8.7 `api/v1/deps.py`: `survey(request, uuid, role)` = `survey_for` + `require_pro_api`, `forbidden_role` when visible but under-privileged; `layer_for` in `api/rights.py`
- [x] 8.8 `/.well-known/oauth-protected-resource/api/` + `invalid_token(resource_metadata=…)` for API 401s
- [x] 8.9 `api_token_first_use` emitted in `api.auth.authenticate` on first use (+ event name in `product_events`)
- [x] 8.10 Move `/api/v1/me` onto the router; `api/tests/test_me.py` unchanged and green

## 9. Resources

- [x] 9.1 Schemas (`api/v1/schemas/`): In models with `extra='forbid'`, Out models; `forms_bridge.py` mapping In → form data dicts
- [x] 9.2 Surveys: list (with `hidden_by_plan`), create (workspace resolution), get, patch (per-field role), delete (trash, `cap.survey_delete`), `cap.survey_create` on create
- [x] 9.3 Lifecycle: publish (`review`), close, draft create, draft publish (`force`, `incompatible_draft`), draft discard; draft-copy guard on publish/close
- [x] 9.4 Sections: list, create, get, patch, delete (`acknowledge_answer_loss`), order
- [x] 9.5 Questions: list per section, create, subquestion create, get, patch, delete, order, choices
- [x] 9.6 Layers: list (deferred geometry), geojson via `layers.cached_geojson_response` extracted from `survey_layer_geojson`
- [x] 9.7 Import: `POST /surveys/import` (multipart, `cap.survey_import`, 202), `GET /import-jobs/{id}` own jobs only
- [x] 9.8 Responses: paginated sessions via `analytics.nonempty_sessions`, ordinals, answers by code, no IP/UA
- [x] 9.9 Export: `export.export_response(...)` extracted from `download_data` (view switched), API route with `cap.export` and `data_exported` `surface='api'`

## 10. Tests (the issue's security checklist)

- [x] 10.1 `api/tests/test_v1_contract.py`: OpenAPI valid (openapi-spec-validator if present, else schema shape), every operation has security, all codes listed; unknown route envelope
- [x] 10.2 `test_v1_rights.py`: scope before body; responses scope; other workspace 404; viewer write 403 `forbidden_role`; question under wrong survey 404; Free workspace `pro_required`
- [x] 10.3 `test_v1_schemas.py`: forbidden fields 422 never applied (organization, status, owner, geojson_gz); script in subtext same bytes as editor; redirect_url cases; strict visibility rule
- [x] 10.4 `test_v1_live.py`: structural on published → `draft_required`; content edit applied + rescreen called; draft create → edit → publish flow; held publish → `review: pending` and respondent URL unavailable
- [x] 10.5 `test_v1_lists.py`: limit clamp; cursor from another survey 400; tampered cursor 400; empty sessions hidden by default
- [x] 10.6 `test_v1_data.py`: export parity with `download_data` (xlsx), `data_exported` with `surface='api'`; import job ownership; layers list query capture (extend `LayerMemoryDietTest`); gzip passthrough
- [x] 10.7 `test_v1_http.py`: CORS preflight from `https://evil.example` without credentials header; 500 envelope without traceback and PostHog without bearer; 401 `resource_metadata`; first-use event once
- [x] 10.8 `./run_tests.sh api` + `./run_tests.sh survey` green

## 11. Docs and ship

- [x] 11.1 `api/README.md`: REST section (routers, schemas, errors, how to add an endpoint)
- [x] 11.2 Help centre: `help/src/content/docs/reference/api.md` (generated from `openapi.json` by a script in `help/scripts/`) + `how-to/getting-started-with-the-api.md` (curl, Python, QGIS note); `help_links` key; `npm run build` green
- [x] 11.3 `survey/changelog/<date>-rest-api.html` entry
- [x] 11.4 `CLAUDE.md`: API platform paragraph extended with `/api/v1/` rules
- [x] 11.5 PR 2 opened (#397, merged 2026-10-23); production smoke: openapi.json 200, 401 envelope with resource_metadata and no cf-mitigated for a bot UA, RFC 9728 document, CORS preflight. (The "Cloudflare skip rule" step was void: the edge is Render's, not ours.)
