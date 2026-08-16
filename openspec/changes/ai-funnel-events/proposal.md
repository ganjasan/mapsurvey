# AI drafting in the creator funnel

## Why

Two changes landed on the same day and left a hole between them.

`posthog-funnel-migration` (#75) put the creator funnel in PostHog: six events, every
historical one backfilled, and `creation_method` riding on `survey_created` from the
start — `manual` for all history, `CREATION_AI` defined but never emitted, because the
AI generator did not exist in master when that branch was written.

`ai-survey-generator` (#59) shipped the generator hours later. It creates surveys through
`materialize_draft()` inside a Celery task, not through `editor_views.create_survey`, and
`survey_created` is emitted in the view. There is no `post_save` receiver on
`SurveyHeader` — `signals.py` only listens to `SurveySession`.

So an AI-drafted survey today produces **no `survey_created` event at all**. Not a
mislabelled one: an absent one. The funnel undercounts every AI creator, the
`manual`/`ai` breakdown that the whole instrumentation exists for reads 100% manual
forever, and the hypothesis behind the AI onboarding bet — *does an AI-drafted first
survey raise registration → first published survey?* — cannot be answered from the tool
built to answer it.

## What changes

Four events, chosen under the constitution `product_events.py` already states: **every
event must also be reproducible historically from a timestamp we already store.**
`AIGenerationEvent` stores a timestamp for each of the four, so a backfill can reconstruct
them for the drafts generated before this ships.

1. **`survey_created` with `creation_method='ai'`** — emitted from the AI flow at the same
   logical moment the view emits its `manual` counterpart. Closes the hole; nothing about
   the existing event's shape changes.

   Alongside it, **`survey_question_added`**, which is the gap that reads *backwards*
   (found in issue #76). That event fires in `editor_question_create` — a human adding a
   question in the editor. An AI draft arrives with its questions already written, so the
   creator never passes through that view. Left alone, the funnel would report AI creators
   as "created a survey, never added a question": the exact drop-off the generator removes,
   displayed as a regression.
2. **`ai_draft_requested`** — the creator submitted a brief. This is the funnel step that
   makes the panel measurable rather than only its successes: brief → draft → published.
   Reproducible from `AIGenerationEvent.created_at`.
3. **`ai_draft_finished`** — one event per terminal outcome, carrying `outcome`
   (`success` / `invalid_draft` / `provider_error` / `error` / `not_configured`), latency
   and token counts. Emitted from `_finish()`, the single terminal point every branch
   already funnels through. Reproducible from the row's `outcome`, `latency_ms` and usage
   fields.
4. **`ai_draft_opened`** — the creator was still on the page when the draft landed and got
   redirected into the editor. This is deliberately *not* a `waited` property on
   `ai_draft_finished`: `redirected_at` is written later, by the status endpoint, so at
   `_finish()` time nobody knows yet whether the creator waited. A property would have to
   guess; a second event states the fact when it becomes true. Reproducible from
   `redirected_at`.

The gap between (3) with `outcome='success'` and (4) is the abandonment measure the whole
loading-overlay design was worried about — how many creators walk away mid-generation.

A management command backfills all three for existing `AIGenerationEvent` rows, reusing
the historical-migration client and the `uuid5` idempotency of
`backfill_posthog_events`.

## What does not change

- **No respondent data.** These are creator events, the boundary from
  `posthog-internal-analytics` holds unchanged.
- **The brief text is never sent to PostHog.** `ai_draft_requested` carries the shape of
  the request (language count, whether a use case was picked), never its content. The
  brief is customer project description; it already goes to one processor and does not
  need a second.
- **No new model fields, no migration.** Everything emitted is already stored.
- **The admin funnel dashboard keeps computing what it computes.** Slimming it stays out
  of scope, same as in #75.

## Impact

- `survey/product_events.py` — three new event-name constants and their property contracts
- `survey/ai/generation.py` — `_finish()` emits the terminal events, including the
  `survey_created` that was missing
- `survey/editor_views.py` — `ai_draft_requested` where the brief is accepted,
  `ai_draft_opened` where the status endpoint issues its `HX-Redirect`
- `survey/management/commands/backfill_ai_events.py` — new
- `survey/tests.py` — emission asserted per outcome, brief text asserted absent
