## Context

Generation runs in a Celery worker; the create page polls `editor_generation_status` every 2s and
gets a 204 until the outcome is terminal. The provider makes one blocking call and returns a parsed
blob plus usage. `ai-generation-latency-telemetry` established that the whole creator-visible wait
is inside that call — under 1.3s belongs to everything else — so the only place progress can come
from is the call itself.

Anthropic's implementation already streams internally (`messages.stream` +
`get_final_message()`, because the SDK refuses large `max_tokens` otherwise) and discards the
increments. Gemini's does not stream at all. So one provider throws away exactly what we now want,
and the other never asks for it.

The overlay is a fixed full-screen card polled by a separate hidden element with `hx-swap="none"`,
a shape arrived at because swapping the overlay itself restarted its animations and read as
flicker. Any progress mechanism has to preserve that.

## Goals / Non-Goals

**Goals:**

- Show the creator something true about their draft while it is being written.
- Keep the no-fabricated-stages rule the current overlay defends — progress must be derived from
  content the model actually produced.
- Leave validation, materialization, retry and error handling structurally unchanged: this changes
  how the blob arrives, not what happens to it.
- Keep a provider that cannot stream fully conformant.

**Non-Goals:**

- A percentage or an ETA. We do not know how many sections the model will write, and inventing a
  denominator is the same lie in a different costume.
- Reducing latency. This change makes the wait legible; `AI_THINKING_LEVEL` is the lever that makes
  it shorter.
- Streaming to the browser directly (SSE/WebSocket from Django). The generation is in a worker, the
  page already polls, and adding a second transport for a 2s-granularity counter is not worth the
  deployment surface.

## Decisions

### D1. Streaming is an optional callback on the existing method, not a second method

`complete_structured(..., on_progress=None)`. When supplied and the provider can stream, it is
called with a snapshot of counts as content arrives; otherwise it is never called and behavior is
byte-identical to today.

A separate `complete_structured_streaming()` would fork the error taxonomy, the truncation check and
the schema adaptation — the exact per-provider divergence `client.py` exists to prevent. An optional
parameter keeps one code path with one place that raises `TruncatedOutput`.

The callback returns nothing and its exceptions are swallowed by the provider: progress reporting
must never be able to fail a generation that is otherwise succeeding. A draft lost because a
progress write hit a database hiccup would be a strictly worse product than no progress at all.

### D2. Progress is counted by an incremental structural scan, in its own module

`survey/ai/progress.py` holds a `DraftProgress` scanner: it is fed accumulated text and reports how
many objects have closed inside the top-level `sections` array, and how many inside the `questions`
arrays within them. It tracks brace depth and string/escape state so that a `{` inside a question's
label text cannot be miscounted.

In its own module and free of HTTP, Django and provider specifics, because it is the one genuinely
fiddly piece of logic here and it deserves to be testable by handing it strings. It is also the part
most likely to need adjustment if the draft schema changes shape.

*Alternative considered:* repeatedly attempting `json.loads` on the accumulated text with closing
braces appended. Rejected — it is O(n) parses over a growing string, and "repair the JSON and see if
it parses" fails in ways that depend on where the chunk boundary happened to fall.

*Alternative considered:* counting a marker substring such as `"questions"`. Rejected — it counts
occurrences in creator-visible text as readily as in structure, which is how a counter starts lying.

### D3. Counts are persisted on the event, written only when they change

The worker cannot talk to the polling request, so the row is the channel — the same reasoning that
already put `last_polled_at` and `redirected_at` there, and the same benefit: a worker restart
leaves a visible partial state rather than a silently lost one.

Writes use `queryset.update()` on the changed fields only, and only when a count actually increased.
A section closing is a handful of events per generation, not a per-chunk write storm. `update()`
rather than `save()` for the reason already documented at the status endpoint: the worker and the
poller write this row concurrently, and a load-modify-save could clobber a terminal outcome with a
stale `pending`.

### D4. The status endpoint answers 204 unless progress moved

While pending, the endpoint compares the stored counts against what the client says it already has
(sent as a query parameter by the poller) and returns a small fragment only when they differ. The
existing hidden-poller-plus-`hx-swap="none"` arrangement is kept for the terminal cases; the
progress fragment targets a dedicated element inside the card, so the card, its spinner and its
fade-in are never re-rendered.

Sending the client's known state rather than diffing server-side per session keeps the endpoint
stateless and free of a per-poll write, which matters because it is hit every 2 seconds for the
length of the wait.

### D5. The quips stay, and the comment that forbade fake progress is updated rather than deleted

Reasoning happens before any content streams — with `AI_THINKING_LEVEL` at `medium` that is a
meaningful opening stretch where the honest count is zero. Deleting the quips would replace flavour
with an unmoving "0 sections", which reads as broken. They stay for that window, and the counter
appears beneath once the first section closes.

The template comment is rewritten to say why the rule it states is still being followed, not removed
as though the rule had been wrong. Someone will read that comment next year while adding a stage,
and the reasoning is the part worth keeping.

## Risks / Trade-offs

- **The scanner miscounts if the draft schema's shape changes** (e.g. sections nested differently).
  → It is unit-tested against the real schema's output and fails toward under-counting rather than
  over-counting; a wrong count is cosmetic and cannot affect the draft that gets saved.
- **Streaming changes how provider errors surface**: a non-2xx can arrive after headers, mid-stream.
  → The Gemini path checks status before consuming the body, and a mid-stream failure raises
  `ProviderError` like any other, landing on the existing `provider_error` outcome. The attempt is
  still counted by the accounting added in the previous change.
- **`usageMetadata` arrives on the final chunk of a stream**, so a stream that dies mid-way has no
  usage. → Same as today's connection error: no usage recorded, attempt counted. The previous
  change's `attempts`-without-`total_latency_ms` case already covers exactly this shape.
- **Two writes per generation become a handful.** → Bounded by section count, on a table with three
  rows.
- **Read timeouts behave differently when streaming.** `requests` applies the timeout between
  chunks rather than to the whole call, so a slow-but-alive stream can now outlast
  `AI_REQUEST_TIMEOUT_SECONDS` where before it would have been cut off. → The Celery task's
  `SOFT_TIME_LIMIT = 300` remains the outer bound, which is what it was written to be.

## Migration Plan

One additive migration, nullable integer counts, no data migration. The overlay and endpoint changes
are backward compatible in both directions: an old page polling a new endpoint gets 204s and behaves
exactly as before, and a new page polling for an event that never recorded counts simply never shows
the counter.

Per the repository's deploy constraint, the commit carrying the migration must not also touch
`preDeployCommand`.

## Open Questions

- Should the counter also appear for the Anthropic provider on day one? The wiring is the same
  callback and the SDK already exposes the increments, so it is included — but it is untested against
  a live Anthropic key here, since production runs Gemini.
- Does a visible counter actually change abandonment? `redirected_at` measures it, and there is no
  baseline worth comparing against yet — two waits by one internal user. Worth revisiting once
  external creators generate drafts at all.
