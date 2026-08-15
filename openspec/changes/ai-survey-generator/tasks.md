# Tasks — ai-survey-generator

## 1. Plumbing (no LLM calls yet)

- [x] 1.1 Add `anthropic` to Pipfile; install into venv
- [x] 1.2 `mapsurvey/settings.py`: `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `AI_SURVEY_DRAFT_MODEL` (default `claude-opus-5`), `AI_REQUEST_TIMEOUT_SECONDS` (default 120); `.env.example` block in the GSC/Plausible comment style
- [x] 1.3 `survey/models.py`: `AIGenerationEvent` (kind/user/organization/created_survey SET_NULL, brief+languages JSON, provider, model, tokens, latency_ms, outcome incl. `pending`, error_detail, created_at, indexes on kind+created_at, outcome) + migration
- [x] 1.4 `survey/admin.py`: read-only `AIGenerationEventAdmin` (list_display, list_filter kind/outcome, no add/change)
- [x] 1.5 `survey/ai/__init__.py`, `survey/ai/quota.py` (`QuotaExceeded`, no-op `check_quota()` with #87 docstring)

## 2. AI core (unit-testable with a fake provider)

- [x] 2.1 `survey/ai/client.py`: `NotConfigured`/`ProviderError`, `LLMUsage`, `LLMProvider` protocol (`complete_structured`), `get_provider()` by `AI_PROVIDER`, `provider_configured()`; `AnthropicProvider` via official SDK — streaming call + `get_final_message()`, `output_config` json_schema, `max_retries=1`, explicit timeout, `stop_reason` handling (refusal→ProviderError, max_tokens→truncated flag), usage extraction
- [x] 2.2 `survey/ai/schema.py`: content-only JSON schema (sections→questions→choices, one-level `sub_questions`, `{lang: text}` dicts, no structural fields, `additionalProperties: false`) + TypedDict IR docs
- [x] 2.3 `survey/ai/prompts.py`: system prompt (geo bias to point, 2–4 sections, one primary geo question with 1–2 sub-questions, integer choice codes, ascending range/rating codes, all requested languages, do NOT emit structural fields) + `build_user_prompt(brief, languages)` with use-case steering
- [x] 2.3a Marker styling: `color` + curated-icon `icon` in schema/validator/materializer/prompt (sentinel "none" — Gemini rejects "" in enums)
- [x] 2.3b Server-side hypothesis telemetry on `AIGenerationEvent`: `generated_blob` snapshot, `last_polled_at`, `redirected_at` (queryset .update() against worker races)
- [x] 2.3c Ground the prompt in the PPGIS literature and describe the respondent-facing interface: `docs/research/survey-design-rules.md` (rules + citations, shared source), `PLATFORM_DESCRIPTION` + `DESIGN_RULES` blocks in prompts.py, same rules added to the `newsurvey` skill; commit the source papers alongside
- [x] 2.4 `survey/ai/validator.py`: `validate_blob(blob, requested_languages) -> list[str]` implementing the D5 rules (pure, no I/O)
- [x] 2.5 `survey/ai/materialize.py`: IR→envelope conversion (compute codes/is_head/links/order_number, lang-dicts→translations lists, header overrides merge, WKT from map fields) → in-memory ZIP → `import_survey_from_zip`; returns (survey, warnings)
- [x] 2.6 `survey/ai/generation.py`: `SurveyBrief` dataclass, `generate_survey_draft(event)` orchestrator — check_quota → prompt → provider call → validate (one retry with error list) → atomic{materialize + owner SurveyCollaborator} → event update in `finally`
- [x] 2.7 `survey/ai/tasks.py`: `@shared_task generate_survey_draft_task(event_id)` with `soft_time_limit=300`, marks event `error` on unexpected exception

## 3. Forms, views, URLs

- [x] 3.1 `survey/editor_forms.py`: `USE_CASE_CHOICES`, `SurveyBriefForm` (goal required-on-generate, audience/map_target optional, use_case)
- [x] 3.2 `survey/editor_views.py`: `editor_survey_create` branch on `action` (`empty` default path byte-identical; `generate` validates both forms, creates pending event, enqueues task, returns polling partial); `editor_generation_status(event_id)` view (owner check; pending→spinner partial, success→`HX-Redirect`, failure→message partial with re-bound forms)
- [x] 3.3 `survey/urls.py`: status URL
- [x] 3.4 `survey/views.py` `editor()`: zero-survey redirect (role-gated, `?dashboard=1` escape, `is_canonical=True, deleted_at__isnull=True` `.exists()` check)

## 4. Templates

- [x] 4.1 `survey/templates/editor/survey_create.html`: AI brief panel gated on `provider_configured`, use-case chips, two submit buttons, privacy notice, disable-on-submit + polling wiring (`hx-trigger="every 2s"`), "Skip to dashboard" link on `?welcome=1`, Cancel → `?dashboard=1`
- [x] 4.2 `survey/templates/editor/partials/generation_status.html`: spinner / error fragment + game-style rotating flavor quips (shuffled JS array, ~3s cycle, no progress claims)

## 5. Deployment config

- [x] 5.1 `render.yaml`: enable worker previews; add `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL` (`sync: false`) plus an explicit `AI_PROVIDER` to web + worker. Provider is declared, not defaulted: prod runs Gemini (no Anthropic billing), and the panel gate reads the selected provider's key only
- [x] 5.2 `.env.ports.example` / docs untouched — verify docker-compose celery picks up new env via `.env`

## 6. Tests (GIVEN/WHEN/THEN, survey/tests.py)

- [x] 6.1 Validator tests: valid blob passes; wrong language key set; two top-level geo; all-html; empty/duplicate/non-integer choice codes; non-ascending rating codes; section count bounds; geo sub-question rejected
- [x] 6.2 Materializer tests: computed is_head/links/codes/order; translations per language; choice dicts intact; atomic rollback on forced failure
- [x] 6.3 Client tests: `NotConfigured` when key empty; provider error normalization (mocked SDK); no vendor import outside client
- [x] 6.4 Generation flow tests (CELERY_TASK_ALWAYS_EAGER + fake provider): success creates survey+collaborator+event; invalid-twice → `invalid_draft`, exactly 2 calls, no survey; provider error path
- [x] 6.5 View tests: create page hides panel when unconfigured; `action=empty` and legacy POST regression; generate → pending event + polling fragment; status endpoint owner check; success poll → `HX-Redirect`
- [x] 6.6 Dashboard redirect tests: zero-survey redirect, `?dashboard=1` escape, org-with-surveys no-op, viewer no-op
- [x] 6.7 Run full suite `./run_tests.sh survey -v2` — one baseline, one after-changes

## 7. Smoke (done with Gemini; Anthropic path unverified — billing blocked)

- [x] 7.1 Local end-to-end with a real key in `.env` (never committed): generate a 2-language draft, open in editor, verify respondent preview renders
