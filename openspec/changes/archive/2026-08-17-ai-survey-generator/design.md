# Design — AI Survey Draft Generation

## Context

The Create New Survey page (`/editor/surveys/new/`, `editor_survey_create`) today produces
an empty survey (one default section) — the biggest activation leak. We add a one-shot
"brief + structured hints" panel (mockup variant B, `interaction-modes.mockup.html`) that
generates a fully populated multilingual draft via the Anthropic API and lands the creator
in the editor. Three codebase facts shape the design: the serialization import path
(`survey/serialization.py`) is the one battle-tested door into the survey data model; there
is **no** streaming infrastructure anywhere; Celery exists (Redis broker, newsletter task)
but its worker is currently disabled on PR previews. Three architecture explorations
(minimal / clean / pragmatic) were run; the approved architecture is the C+B hybrid with
async execution.

## Goals / Non-Goals

**Goals:**
- Creator fills name, languages, map position + goal/audience/map-target/use-case → clicks
  "Generate draft" → lands in `editor_survey_detail` with a populated draft.
- All selected content languages generated in one model call (base fields + `translations`
  rows + per-language choice-name dicts).
- Generated drafts are structurally safe by construction: the model never produces
  `code`, `is_head`, `next/prev_section_name`, `order_number` — the materializer computes
  them from list order.
- Shared `survey/ai/` plumbing reusable by AI analytics (#92) and AI triage (#95); quota
  seam for #87.
- Feature fully verifiable on PR previews (Celery worker previews enabled).
- `ANTHROPIC_API_KEY` unset ⇒ AI panel absent, everything else untouched.
- Every attempt logged (`AIGenerationEvent`) for funnel/cost measurement.

**Non-Goals:**
- Conversational chat mode / token-by-token streaming (future iteration; mockup variant C).
- Quotas, Pro-tier gating, Turnstile on the endpoint (no-op `check_quota()` seam only).
- Question images, `validation_settings`, thanks-page content in generated drafts.
- Editing existing surveys via AI; generation is creation-time only.
- Reproducing the mockup's fake per-step progress texts (no real progress signal exists).

## Decisions

### D1. Execution: Celery task + HTMX status polling (not sync request)

Generation (~20s single-language, potentially 60s+ multilingual) runs in a Celery task.
The create view enqueues, returns a "generating" partial; the page polls a status endpoint
(`hx-trigger="every 2s"`); on success the endpoint answers with `HX-Redirect` to the
populated editor.

- *Why not sync in-request:* prod web is 2 workers × 4 gthread threads on 0.5 CPU;
  gunicorn's gthread timeout kills a whole worker (4 threads) when it wedges past
  `GUNICORN_TIMEOUT`. Sync would force a <45s ceiling and a language soft-cap —
  contradicting the "all languages at once" decision.
- *Why Celery is now acceptable:* the sole objection (worker absent on PR previews) is
  removed by enabling worker previews in `render.yaml` (small prorated cost). Local dev
  already runs a celery service in docker-compose; tests use `CELERY_TASK_ALWAYS_EAGER`.
- Worker `--concurrency 2` naturally caps parallel generations — no Redis semaphore.
- Task state lives in a DB row (`AIGenerationEvent.outcome='pending'` → terminal), not in
  Celery result backend — the status endpoint reads the row; survives worker restarts and
  is queryable in admin. User closes tab ⇒ task completes, survey waits in dashboard.

### D2. Provider-agnostic client with an Anthropic implementation

`survey/ai/client.py` defines a thin provider interface so the platform is not bound to a
single LLM vendor (EU-data-residency demands in German deals and the backlog's
"self-hostable local model later" both make this a real, not speculative, requirement):

```python
class LLMProvider(Protocol):
    def complete_structured(self, *, system: str, user: str,
                            schema: dict, max_tokens: int) -> tuple[dict, LLMUsage]: ...
def get_provider() -> LLMProvider  # by settings.AI_PROVIDER; raises NotConfigured
```
- **`AnthropicProvider`** is the production path, using the official `anthropic` SDK
  (new Pipfile dependency): typed errors, controlled retries (`max_retries=1`), explicit
  `timeout=`, streaming helpers.
- **`GeminiProvider`** (Google AI Studio) ships alongside it over plain `requests` — no
  second vendor SDK in the production image. Its free tier is what makes end-to-end
  verification possible without a funded account, and it proved the seam works: adding it
  touched only `client.py`, leaving prompts, validator, materializer and orchestrator
  untouched. Selected with `AI_PROVIDER=gemini`; `GEMINI_MODEL` is env-configurable
  because Google renames models frequently.
- Provider classes declare `configured()`, so `provider_configured()` (the UI gate) does
  not grow a branch per provider.
- Gemini's structured output is a JSON Schema *subset* — `additionalProperties` is
  rejected and type names are uppercase — so `client._to_gemini_schema()` adapts our
  schema at the boundary rather than making `schema.py` speak every dialect.
- Provider errors are normalized to the module's `NotConfigured`/`ProviderError` — nothing
  outside `client.py` imports a vendor SDK.
- Structured-output enforcement is a per-provider detail; providers without native JSON
  schema support fall back to prompt-embedded schema + the same `validate_blob()` retry
  loop (the validator is the real gate; D5).
- Model: `settings.AI_SURVEY_DRAFT_MODEL`, default **`claude-opus-5`** (backlog mandates
  the most capable model; quality of the first draft is the value prop). Env-overridable.
- Structured output via `output_config: {format: {type: "json_schema", schema: ...}}` —
  guarantees parseable JSON, no prose parsing, no forced-tool workaround.
- **Schema must be non-recursive** (structured-outputs limitation): `sub_questions` is a
  separate one-level `SubQuestion` type without its own `sub_questions` — matching the
  editor UI, which only exposes one nesting level anyway.
- Long multilingual outputs: call via `client.messages.stream(...)` +
  `get_final_message()` inside the task (SDK requires streaming for large `max_tokens`;
  we set `max_tokens` ≈ 64000). Client `timeout` generous (default 120s read) since no
  gunicorn ceiling applies in the worker.
- Thinking: leave the model default (adaptive); no `thinking` parameter sent.

### D2b. Prompt content is grounded in the PPGIS literature, not in intuition

The system prompt is an operative summary of `docs/research/survey-design-rules.md`,
which carries the citations (Brown & Kyttä 2014; Seebauer et al. 2024; Lehnert et al.
2023; Alderton et al. 2026; Laborgne & Klöcker 2023) alongside this platform's own
answer-rate figures. Two things changed once the literature was read rather than
assumed: the prompt now asks for a *current-behaviour* question (without it "not
affected" and "coping alone" are indistinguishable) and for *assets*, not only problems.
Both showed up in the first live generation after the change.

The prompt also describes the respondent-facing interface — sections as screens, popup
sub-questions on a mapped feature, sub-question names becoming GeoJSON field names.
Nothing in the JSON schema communicates that, so without it the model cannot know that
attributes on a mapped object are only expressible as sub-questions.

Same rules were added to the `newsurvey` assistant skill: one source, two consumers.

### D3. Structural fields are computed, never generated

The JSON schema given to the model contains **only content**: sections (name-free), titles,
subheadings, questions (name, subtext, input_type, required, choices, sub_questions),
all text as `{lang: text}` dicts. `materialize.py` walks list order and injects
`code = S{i+1}` / `question_code_generator()`, `is_head = (i == 0)`,
`next/prev_section_name` from adjacency, `order_number = j+1`. This eliminates by
construction every silent import gotcha found in exploration (stuck-in-draft, broken nav
links, duplicate codes). *Alternative rejected:* validating model-produced structural
fields — detection instead of prevention, more validator code, still racy on global code
collisions.

### D4. Materialization through `import_survey_from_zip` (one door)

`materialize.py` converts the validated IR into the exact `{"version": "1.0", "survey":
{...}}` envelope, writes it as `survey.json` into an in-memory ZIP, and calls
`serialization.import_survey_from_zip(buf, organization=, created_by=)`. Header overrides
(name, `available_languages`, map WKT/zoom/basemap from the same POST fields the manual
flow reads) merge into the envelope top level.
- *Why:* reuses `transaction.atomic()`, the input_type whitelist, choices-required checks,
  global code-collision remap, translation creation — all covered by existing tests.
- `SurveyCollaborator(role='owner')` is created by the orchestrator afterwards (the import
  path deliberately doesn't), inside one outer `transaction.atomic()` with materialization.
- *Alternative rejected:* calling internal `create_survey_header`/`create_sections`
  directly (architect B) — saves an in-memory ZIP but bypasses `validate_archive` and
  couples to private functions.

### D5. Validation: pure `validate_blob()` gate before any DB write

Rules (error list, `[]` = OK): 2–4 sections; ≥1 answerable (non-`html`) question; every
text dict has exactly the requested language key set; `input_type` ∈
`serialization.VALID_INPUT_TYPES`; choice/multichoice/range/rating have non-empty choices
with unique integer codes, range/rating strictly ascending; ≤1 top-level geo question,
biased to `point`, with 0–2 sub-questions none of which is geo
(`SUBQUESTION_DISALLOWED_INPUT_TYPES` imported, not duplicated). One bounded retry: on
validation failure the task re-asks the model once with the error list; second failure ⇒
`invalid_draft`, nothing written.

### D6. Package layout `survey/ai/` (shared plumbing)

```
survey/ai/__init__.py
survey/ai/client.py       # LLMProvider interface + AnthropicProvider; NotConfigured/ProviderError
survey/ai/prompts.py      # system prompt + brief interpolation (python constants)
survey/ai/schema.py       # JSON schema for output_config + TypedDict IR docs
survey/ai/validator.py    # validate_blob() — pure, no I/O
survey/ai/materialize.py  # IR → envelope → in-memory ZIP → import_survey_from_zip
survey/ai/quota.py        # check_quota() no-op seam for #87
survey/ai/generation.py   # orchestrator generate_survey_draft() — callable sync or from task
survey/ai/tasks.py        # @shared_task generate_survey_draft_task(event_id)
```
#92/#95 later add sibling modules reusing `client.py` + `AIGenerationEvent` (`kind` enum).
The orchestrator takes no request/response — swapping to a chat flow later replaces
prompt/call steps only.

### D7. `AIGenerationEvent` model (one migration)

`kind` (choices, `survey_draft` now), `user`/`organization`/`created_survey` (SET_NULL),
`brief` JSONField (stored — needed to iterate on prompt quality; it is creator-authored
project description, not respondent data), `languages` JSONField, `provider`, `model`,
`input_tokens`/`output_tokens`/`latency_ms`, `outcome`
(`pending/success/not_configured/provider_error/invalid_draft/error`), `error_detail`,
`created_at`, plus server-side hypothesis telemetry: `generated_blob` (the draft as the
model produced it — diffing against the published survey measures manual repair),
`last_polled_at` (each 2s poll stamps it, so its freeze marks when the creator stopped
waiting) and `redirected_at` (the HX-Redirect being issued proves the creator waited;
first stamp wins). All three are written server-side — no client JS to lose. Doubles as
the task-state row (D1) and the future quota substrate (#87 counts rows). Read-only
admin registration.

### D8. View/UX flow

- `editor_survey_create` branches on submit `action`: `empty` (byte-identical today's
  path, also the default for legacy POSTs) vs `generate` (validate `SurveyCreateForm` +
  new `SurveyBriefForm`; create `AIGenerationEvent(outcome='pending')`; enqueue task;
  render the polling partial into the page via HTMX).
- New URL `editor_generation_status/<event_id>` (login + org check + event.user == request.user):
  pending ⇒ 200 partial with spinner (polling continues); success ⇒ `HX-Redirect` to
  `editor_survey_detail`; failure ⇒ partial with a friendly per-outcome message and the
  re-enabled form (brief preserved).
- The whole AI panel renders only when `client_configured()` (key set) — Turnstile-style
  dev degradation; "Create empty" always present.
- Game-style loader (Hearthstone/Terraria pattern): indeterminate spinner + "This can
  take a minute…" + a rotating line of flavor quips (client-side JS array, ~3s cycle,
  shuffled; e.g. "Sharpening map pins…", "Consulting the cartographers…", "Teaching
  questions to behave…"). Quips are entertainment and deliberately claim no pipeline
  progress — fake *progress steps* remain out (they would be disconnected from reality).
- Privacy notice (mockup copy): brief is processed by Anthropic Claude; survey answers
  are never sent to AI providers.
- New-user redirect in `views.editor()`: role can create + `?dashboard=1` absent + org has
  0 canonical non-deleted surveys ⇒ redirect to create page `?welcome=1`; template then
  shows "Skip to dashboard" (→ `/editor/?dashboard=1`). The existing Cancel link changes
  to carry `?dashboard=1` to avoid a redirect loop.

### D9. Configuration & deployment

- `settings.py`: `AI_PROVIDER` (default `anthropic`), `ANTHROPIC_API_KEY` (`''` = off),
  `AI_SURVEY_DRAFT_MODEL` (default `claude-opus-5`), `AI_REQUEST_TIMEOUT_SECONDS`
  (default 120). `.env.example`
  documents them in the GSC/Plausible comment style; public repo ⇒ no secret defaults.
- `render.yaml`: `ANTHROPIC_API_KEY` with `sync: false` on **web** (form gating +
  status view need only the flag — actually only truthiness; key still needed by worker
  which makes the calls; put the key on both web and worker for simplicity since web
  gates the UI on its presence) and **worker**; worker `previews: generation` turned on.
- Pipfile: `anthropic` added.

## Risks / Trade-offs

- [Worker queue shared with newsletter sends] → newsletter chunks are short; at current
  volume interleaving is fine. If contention appears, add a dedicated queue name later.
- [Preview worker cost] → prorated Starter (~cents/day per open PR); accepted explicitly.
- [Model output quality across 75 languages] → validator enforces language-key
  completeness; base-language fallback never fires silently for *missing* languages (that
  is a validation error), quality of translation itself is measured via user edits later.
- [`AIGenerationEvent.brief` stores free text] → creator-authored, our DB only; privacy
  notice discloses processing by Anthropic; revisit at DPA work (#88).
- [Polling every 2s per waiting user] → trivial load (status view is one indexed PK read).
- [SDK retries + our one validation retry could stack latency] → SDK `max_retries=1`,
  client timeout 120s, task `soft_time_limit=300`.
- [`stop_reason` handling] → task treats `refusal`/`max_tokens` as `provider_error` /
  `invalid_draft` respectively; never parses content without checking `stop_reason`.

## Migration Plan

1. Migration adds `AIGenerationEvent` only (no changes to existing tables) — safe,
   additive; deploy order irrelevant.
2. `render.yaml` change enables worker previews + adds env var; key set manually in
   Render dashboard (never committed).
3. Feature is dark until `ANTHROPIC_API_KEY` is set — deploy code first, set key after
   smoke-testing on a preview.
4. Rollback: unset the key (panel disappears, zero code path reached); no data migration
   to revert.

## Open Questions

- None blocking. Prompt wording and use-case few-shot seeds will be tuned during
  implementation against real generations on a preview.
