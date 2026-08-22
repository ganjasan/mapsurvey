## Why

Drafting a survey takes 18–50 seconds, and the creator spends all of it looking at a spinner and
rotating flavour text. The overlay's own comment explains why it says nothing real:

> The quips are entertainment, not telemetry: generation is a single opaque model call, so there is
> no honest per-step progress to show.

That is a true statement about a non-streaming call, and the honest thing to have built at the time.
It stops being true the moment we stream: a draft arrives section by section, and "4 sections
drafted so far" is a fact about what the model has actually produced, not a fabricated pipeline
stage. The constraint the comment defends — never imply a stage the backend does not have — is kept;
what changes is that the backend now has one.

Waiting without feedback is also the failure mode most likely to lose a creator at the exact moment
the product is doing its most valuable work. `redirected_at` already tells us whether they were
still there when the draft landed; today both successful generations were waited out, but that is
two data points from one internal user.

## What Changes

- **The provider interface gains optional streaming.** `complete_structured()` accepts an
  `on_progress` callback. Providers that can stream call it as content arrives; providers that
  cannot behave exactly as they do today. No caller is required to pass one.
- **The Gemini provider streams.** It uses the streaming REST endpoint with server-sent events when
  a callback is supplied, accumulating the same JSON it assembles today, so validation,
  materialization and error handling are unchanged in shape.
- **Progress is counted structurally, not guessed.** An incremental scanner tracks how many section
  objects have closed inside the draft's `sections` array and how many questions they contain. This
  is derived from the schema we already control, so it cannot drift into fiction.
- **Progress is persisted and polled.** `AIGenerationEvent` carries the running counts; the existing
  status endpoint returns a progress fragment while pending instead of an unconditional 204, and
  keeps returning 204 when nothing changed so the overlay never re-renders needlessly.
- **The overlay shows what has actually been drafted.** The quips stay — they cover the opening
  stretch when the model is reasoning and nothing has streamed yet — with a real counter beneath
  them once the first section closes.

## Capabilities

### New Capabilities

None. This extends the existing generation capability.

### Modified Capabilities

- `ai-survey-generation`: three requirements change.
  - **Provider-agnostic LLM client** — streaming becomes an optional part of the provider contract,
    surfaced as a progress callback, with non-streaming providers remaining conformant.
  - **Asynchronous generation with status polling** — the status endpoint reports progress while
    pending, and does so without re-rendering the overlay.
  - **Generation event log** — the row carries the running draft counts so progress survives a
    worker restart and is readable afterwards.

## Impact

- `survey/ai/client.py` — `on_progress` on the provider interface; `GeminiProvider` gains an SSE
  path; `AnthropicProvider` wires its existing internal stream to the same callback.
- `survey/ai/progress.py` (new) — the incremental structural scanner, unit-testable in isolation
  and deliberately not aware of HTTP or Django.
- `survey/ai/generation.py` — passes a callback that throttles writes to the event row.
- `survey/models.py` + migration — running counts on `AIGenerationEvent`.
- `survey/editor_views.py` — the status endpoint gains its progress branch.
- `survey/templates/editor/partials/generation_status.html` and the overlay CSS — the progress line,
  and an updated comment recording that the no-fake-stages rule is intact rather than abandoned.
- No respondent-facing surface. No change to what is measured about respondents.
