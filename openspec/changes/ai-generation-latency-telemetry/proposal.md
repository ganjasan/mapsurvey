## Why

Two production generations of near-identical briefs took 49.2s and 17.7s — a 2.8x spread on the
same model (`gemini-3.6-flash`), the same language (`["ru"]`), and near-identical input (1294 vs
1299 tokens). The slow one emitted **fewer** visible tokens than the fast one (1319 vs 2210), so the
time did not go into the output we record. Measurement against `AIGenerationEvent` shows the entire
creator-visible wait is the single provider call: `created_at → redirected_at` was 50.4s and 18.4s
against a recorded `latency_ms` of 49.2s and 17.7s, leaving under 1.3s for Celery hand-off, status
polling, validation and materialization combined.

We cannot say where those 49 seconds went, and the reason is our own instrumentation: the client
records only `candidatesTokenCount` and never `thoughtsTokenCount`, while the provider's reasoning
effort is left at its default instead of being a parameter we set. A latency question about the
product's flagship feature currently has no answer in our data.

## What Changes

- **Reasoning effort becomes an explicit request parameter.** The Gemini provider sends a
  configured thinking level in `generationConfig` instead of inheriting the provider default
  (`medium` for Gemini 3 models). A new setting carries the value so it is tunable per environment
  without a deploy.
- **Thinking tokens are recorded.** `AIGenerationEvent` gains a `thinking_tokens` field, populated
  from the provider's reasoning-token count where the provider reports one. Providers that do not
  report it leave it null — null means "not reported", never zero.
- **Latency is accounted across the whole attempt set, not just the last attempt.** Today `usage` is
  reassigned on every iteration of the retry loop in `generate_survey_draft()`, so a generation that
  retried reports only its final call while the creator waited for all of them. The event gains
  `attempts` and a total elapsed measure covering every provider call in the set, keeping the
  existing `latency_ms` as the terminal call's own duration.
- The AI sub-funnel events already emitted by `product_events` carry the new fields, so the split is
  visible in PostHog as a breakdown rather than requiring a database join.

Not in scope: switching to streaming responses, which is the separate `ai-generation-streaming`
change. No creator-facing behavior changes here.

## Capabilities

### New Capabilities

None. This change deepens an existing capability rather than adding one.

### Modified Capabilities

- `ai-survey-generation`: two requirements change.
  - **Provider-agnostic LLM client** — reasoning effort becomes part of the provider contract:
    a configured thinking level SHALL be sent where the provider supports one, and the provider
    SHALL surface reasoning-token usage alongside input and output tokens.
  - **Generation event log** — the row SHALL additionally carry thinking-token usage, the attempt
    count, and total elapsed across all provider calls in the attempt set, so a retried generation
    is distinguishable from a single slow one.

## Impact

- `survey/ai/client.py` — `LLMUsage` gains reasoning-token and per-call accounting; `GeminiProvider`
  sends the thinking level and reads the reasoning-token count from `usageMetadata`. The Anthropic
  provider is left functionally unchanged but must keep satisfying the widened `LLMUsage` contract.
- `survey/ai/generation.py` — the retry loop accumulates rather than overwrites; `_finish()` writes
  the new fields.
- `survey/models.py` + migration — new nullable fields on `AIGenerationEvent`. Nullable and
  backfill-free by design: the three existing rows genuinely have no such measurement, and writing
  zeros would fabricate one.
- `survey/admin.py` — the read-only event list surfaces the new fields.
- `survey/product_events.py` — `ai_draft_finished` carries the new properties.
- `mapsurvey/settings.py` + `.env.example` — the thinking-level setting.
- No respondent-facing surface, no public API, no change to what is sent to PostHog about
  respondents.
