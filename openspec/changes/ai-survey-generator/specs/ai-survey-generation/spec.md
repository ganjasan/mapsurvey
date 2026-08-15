# ai-survey-generation Specification (delta)

## ADDED Requirements

### Requirement: AI brief panel on the create page
The Create New Survey page SHALL render an AI brief panel — a goal textarea, a "Who will
answer?" input, a "What should they mark on the map?" input, a use-case chip selector
(urban planning / citizen science / school routes / event mapping / other), a privacy
notice, and a "Generate draft" submit — only when an LLM provider is configured
(`AI_PROVIDER` resolvable and its credentials set). The existing "Create empty" path
SHALL remain available and behaviorally unchanged in all cases.

#### Scenario: Provider configured
- **WHEN** an authenticated editor opens `/editor/surveys/new/` and the key for the selected `AI_PROVIDER` is set
- **THEN** the AI brief panel with the "Generate draft" button is rendered alongside the existing name/languages/map fields, including a privacy notice stating the brief is processed by the AI provider and that survey answers are never sent to AI providers

#### Scenario: Provider not configured
- **WHEN** the key for the selected `AI_PROVIDER` is empty
- **THEN** the AI panel is not rendered, the page shows only the manual creation form, and no AI code path can be reached

### Requirement: Asynchronous generation with status polling
A "Generate draft" submission SHALL create an `AIGenerationEvent` row with
`outcome='pending'`, enqueue a Celery task, and return a polling fragment. The page SHALL
poll a status endpoint (HTMX, ~2s interval) that is restricted to the requesting user;
on success the endpoint SHALL respond with an `HX-Redirect` to the populated survey's
editor; on failure it SHALL return a friendly per-outcome message with the form re-enabled
and the brief text preserved.

#### Scenario: Successful generation redirects to populated editor
- **WHEN** the generation task completes successfully
- **THEN** the next status poll responds with `HX-Redirect` to `/editor/surveys/<uuid>/` and the survey contains the generated sections and questions with the requesting user as owner collaborator

#### Scenario: Generation still running
- **WHEN** the status endpoint is polled while the event is `pending`
- **THEN** it returns a 200 fragment with an indeterminate spinner and polling continues

#### Scenario: Status endpoint access control
- **WHEN** a user polls the status endpoint for an event created by a different user
- **THEN** the request is rejected (404/403) and no event information is disclosed

#### Scenario: User closes the tab mid-generation
- **WHEN** the creator navigates away while the task runs
- **THEN** the task completes server-side and the created survey appears in the creator's dashboard

### Requirement: Provider-agnostic LLM client
LLM access SHALL go through a provider interface (`complete_structured(system, user,
schema, max_tokens)`), selected by `AI_PROVIDER` (default `anthropic`). Vendor SDKs SHALL
be imported only inside `survey/ai/client.py`; provider failures SHALL be normalized to
`NotConfigured` (credentials absent) or `ProviderError` (call failed). The Anthropic
implementation SHALL use the official SDK with model `AI_SURVEY_DRAFT_MODEL` (default
`claude-opus-5`), an explicit request timeout, and structured JSON output. A Gemini
implementation (`AI_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`) SHALL be available
over plain HTTP without adding a vendor SDK, adapting the shared schema to that provider's
JSON Schema subset at the client boundary.

#### Scenario: Credentials absent
- **WHEN** the selected provider's credentials are not configured and generation is invoked programmatically
- **THEN** `NotConfigured` is raised before any network call and the event outcome is `not_configured`

#### Scenario: Switching providers changes no other module
- **WHEN** `AI_PROVIDER` selects a different implemented provider
- **THEN** prompts, validation, materialization and the orchestrator behave identically, and only the client's request/response translation differs

#### Scenario: Provider call fails
- **WHEN** the provider API times out, returns a non-2xx error, or refuses the request
- **THEN** the failure is recorded as `provider_error` with detail, nothing is written to survey tables, and the user sees a retry-or-create-empty message

### Requirement: Structural fields are computed, not generated
The JSON schema requested from the model SHALL contain content fields only. The
materializer SHALL compute `code` (sections `S{n}`, questions via
`question_code_generator()`), `is_head` (first section only), `next_section_name`/
`prev_section_name` (list adjacency), and `order_number` (list position). Sub-questions
SHALL be limited to one nesting level.

#### Scenario: Generated survey is structurally sound
- **WHEN** any validated model output is materialized
- **THEN** exactly one section has `is_head=True`, section links form a single chain in list order, every question has a unique code, and `order_number` values are sequential per container

### Requirement: Validation gate before persistence
Model output SHALL pass `validate_blob()` before any database write: 2–4 sections; at
least one answerable (non-`html`) question; every localized text dict has exactly the
requested language key set; `input_type` within the serialization whitelist;
choice/multichoice/range/rating questions have non-empty choices with unique integer
codes (strictly ascending for range/rating); at most one top-level geo question with 0–2
non-geo sub-questions. On validation failure the task SHALL retry the model exactly once
with the error list; a second failure SHALL record `invalid_draft` and write nothing.

#### Scenario: Invalid output retried once then rejected
- **WHEN** the model returns output failing validation twice in a row
- **THEN** exactly two provider calls are made, no `SurveyHeader` row is created, and the event outcome is `invalid_draft`

#### Scenario: Missing translation is a validation error
- **WHEN** the requested languages are `["en", "de"]` and any question name dict lacks the `de` key
- **THEN** validation fails (silent base-language fallback is not permitted for generated drafts)

### Requirement: Multilingual generation in one call
The system SHALL produce content for all of the survey's `available_languages` in a
single provider call; materialization SHALL populate base fields from
the first language and create `SurveySectionTranslation`/`QuestionTranslation` rows plus
per-language choice-name dicts for every language.

#### Scenario: Two-language survey
- **WHEN** a brief is generated with languages `["en", "it"]`
- **THEN** a single provider call is made, base fields are English, and every section/question has an `it` translation row and every choice name dict contains both `en` and `it` keys

### Requirement: Materialization through the serialization import path
Validated drafts SHALL be materialized by building the `{"version": "1.0", "survey":
{...}}` envelope and passing it through `serialization.import_survey_from_zip` (in-memory
ZIP), with the owner `SurveyCollaborator` created in the same outer transaction. Header
fields (name, languages, map position/zoom, default basemap) SHALL come from the form,
never from the model output.

#### Scenario: Atomic failure
- **WHEN** materialization raises after partial object creation
- **THEN** the transaction rolls back completely — no survey, sections, questions, or collaborator rows remain — and the event outcome records the failure

### Requirement: Generation event log
Every generation attempt SHALL write one `AIGenerationEvent` row carrying `kind`
(`survey_draft`), user, organization, brief, languages, provider, model, token usage,
latency, outcome (`pending/success/not_configured/provider_error/invalid_draft/error`),
error detail, and the created survey FK on success. The model SHALL be registered
read-only in Django admin. `check_quota(organization, kind)` SHALL exist as a documented
no-op precondition called before any provider call.

#### Scenario: Success is measurable
- **WHEN** a generation succeeds
- **THEN** its event row has `outcome='success'`, non-null token counts and latency, and links to the created survey

#### Scenario: Quota seam spends no tokens
- **WHEN** `check_quota` raises `QuotaExceeded` (future #87 behavior)
- **THEN** no provider call is made and the event outcome is recorded without token spend
