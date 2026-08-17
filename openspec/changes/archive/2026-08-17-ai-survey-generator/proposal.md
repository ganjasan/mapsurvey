# AI Survey Draft Generation

## Why

Of 222 real registrations only 53% ever create a survey and 38% add a question — the
empty editor is the single biggest leak in the activation funnel, observed live even in
paying-capable buyers (ThINK Jena call, 2026-07-31). This change turns the Create New
Survey page into a brief: the creator describes their goal, and Claude generates a fully
populated draft (sections, questions with correct input types, choices, translations for
every selected language), landing them in the editor with something to edit instead of an
empty canvas. Backlog #15 (`openspec/backlog/idea-ai-survey-creator-chat-agent.md`,
promoted 2026-08-14); MVP is the one-shot "brief + structured hints" variant validated
against mockups (`interaction-modes.mockup.html`, variant B) — the conversational chat
mode remains a future iteration.

## What Changes

- Create New Survey page (`/editor/surveys/new/`) gains an AI brief panel: goal textarea,
  "Who will answer?", "What should they mark on the map?", use-case chips (urban
  planning / citizen science / school routes / event mapping / other), and a
  "Generate draft" submit alongside the unchanged "Create empty" path.
- New `survey/ai/` package — shared LLM plumbing (provider-agnostic `LLMProvider`
  interface with an Anthropic implementation, `NotConfigured`/`ProviderError`
  convention, prompt building, blob validation,
  materialization through the existing serialization import path, quota seam) designed
  for reuse by AI analytics (#92) and AI response triage (#95).
- Generation runs as a Celery task; the create page polls a status endpoint via HTMX and
  redirects to the populated editor on completion. The Celery worker gets **enabled on PR
  previews** so the feature is verifiable before merge.
- Structural fields (`code`, `is_head`, `next/prev_section_name`, `order_number`) are
  never taken from the model output — the materializer computes them from list order,
  eliminating the known silent import gotchas by construction.
- Multilingual: content for ALL selected survey languages is generated in one model call
  (base-language fields + `translations` + per-language choice-name dicts).
- New `AIGenerationEvent` model logs every attempt (kind, outcome, tokens, latency,
  brief, created survey) for funnel measurement, cost tracking, and as the substrate for
  future quota enforcement (#87). Admin-only read surface.
- New-user routing: `/editor/` redirects to the create page while the active org has no
  surveys (escape hatch: "Skip to dashboard" / `?dashboard=1`).
- No quotas in MVP (login-gated only); `check_quota()` is a documented no-op seam for
  #87. `ANTHROPIC_API_KEY` unset ⇒ the AI panel does not render and nothing breaks
  (GSC/Plausible/Turnstile convention).
- Privacy notice on the create page: the brief is processed by Anthropic Claude; survey
  answers are never sent to AI providers.

## Capabilities

### New Capabilities

- `ai-survey-generation`: the end-to-end draft-generation capability — brief form
  contract, Celery execution + status polling, model output validation rules, structural
  field computation, multilingual materialization, failure taxonomy and UX, generation
  event logging, configuration (`ANTHROPIC_API_KEY` unset = feature off).

### Modified Capabilities

- `survey-editor`: the Survey creation requirement changes — the create form gains the
  optional AI brief panel and a second submit action; `/editor/` gains the zero-survey
  redirect to the create page with an explicit escape hatch.
- `render-deployment`: worker service preview generation changes from `off` to enabled,
  and the web + worker services gain the `ANTHROPIC_API_KEY` (`sync: false`) env var.

## Impact

- **Code**: new `survey/ai/` package (client, prompts, schema, validator, materialize,
  quota, generation, tasks); `survey/models.py` (+`AIGenerationEvent`, one migration);
  `survey/editor_forms.py` (+`SurveyBriefForm`); `survey/editor_views.py`
  (`editor_survey_create` branch + status endpoint); `survey/views.py` (`editor`
  redirect); `survey/urls.py` (+1 status URL); `survey/templates/editor/survey_create.html`;
  `survey/admin.py`; `mapsurvey/settings.py`; `.env.example`; `render.yaml`.
- **Dependencies**: `anthropic` SDK added to Pipfile. Provider access goes through a thin
  `LLMProvider` interface (`survey/ai/client.py`) so a second vendor (EU-hosted, local)
  plugs in as one class; only `client.py` imports vendor SDKs.
- **Infra**: Celery worker previews enabled (small prorated preview cost); Redis/Celery
  already provisioned in prod and docker-compose. `ANTHROPIC_API_KEY` secret added to
  web + worker Render services.
- **Reused unchanged**: `survey/serialization.py` import path (the single door into the
  survey data model), `SurveyCollaborator` owner creation mirrors the manual flow.
- **Not affected**: respondent-facing survey pages, export, analytics, versioning;
  the "Create empty" path stays byte-for-byte today's behavior.
