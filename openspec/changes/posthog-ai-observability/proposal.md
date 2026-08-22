## Why

Two questions about the AI generator currently require SQL against our own database: what
does it cost, and do creators think the drafts are any good. PostHog answers the first out
of the box — its LLM Analytics computes per-generation cost from model and token counts,
with dashboards for spend, latency and error rate — but only for events in its
`$ai_generation` schema, which our `ai_draft_finished` is not. The second question has no
answer at all today: `redirected_at` says a creator waited for the draft, and the
generated-vs-published diff says how much they repaired it, but nobody has ever been able
to just *tell us* whether the draft helped.

A measured baseline exists to validate against: the 2026-08-17 ten-run batch cost $0.067
(~0.7¢ per draft, 19 provider calls, 9 ridden-out failures). What PostHog shows after this
change must agree with those numbers.

## What Changes

- **Every finished generation attempt-set additionally emits a PostHog `$ai_generation`
  event** — model, provider, token counts, latency in seconds, a stable trace id derived
  from the `AIGenerationEvent` row, and error state for failures. **Never content**: no
  brief, no draft, no error text that could quote them. Reasoning tokens are folded into
  `$ai_output_tokens` because Gemini bills them at the output rate — that is what makes
  PostHog's computed cost equal the invoice — and also reported separately.
- **A feedback strip appears in the editor the first time a creator lands in a freshly
  generated survey.** Thumbs up/down plus an optional comment, dismissible, shown once.
  The vote emits PostHog's `$ai_feedback` event carrying the same trace id, so in the LLM
  Analytics UI the rating sits on the exact generation it judges — cost, latency and the
  creator's verdict in one row.
- The success redirect carries the generation event id as a query parameter, which is what
  lets the editor know this arrival deserves the strip.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-survey-generation`: the **Generation event log** requirement additionally requires
  the PostHog LLM-analytics emission with its privacy constraints, and the **Asynchronous
  generation with status polling** requirement gains the feedback strip on the
  post-generation editor arrival.

## Impact

- `survey/product_events.py` — `emit_llm_generation(event)`: the `$ai_generation` capture,
  same never-raises contract as `emit()`.
- `survey/ai/generation.py` — `_emit_terminal_events` calls it.
- `survey/editor_views.py` — the success redirect gains `?draft=<event id>`; the editor
  view passes strip context after verifying the event belongs to the requesting user and
  actually produced this survey.
- Editor template + a small partial — the strip, client-side `posthog.capture` of
  `$ai_feedback` (the PostHog snippet is already on editor pages; absent snippet = strip
  hidden).
- No model changes, no migration.
