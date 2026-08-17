## Context

`AIGenerationEvent` already records provider, model, input/output tokens, latency and outcome, and
that log is what made the latency question askable at all. It is also where the question dies. Three
production rows exist; the two successful ones read:

| id  | latency_ms | input | output | languages | sections |
|-----|-----------|-------|--------|-----------|----------|
| 453 | 49185     | 1294  | 1319   | `["ru"]`  | 3        |
| 454 | 17670     | 1299  | 2210   | `["ru"]`  | 3        |

The slow call produced 27 tok/s of visible output, the fast one 125 tok/s. Same model, same schema,
same language, same section count. Output is not where the time went, and we record nothing else
that could account for it.

Two structural facts constrain the design:

1. `latency_ms` is measured around one HTTP call in `GeminiProvider.complete_structured()`, and
   `generate_survey_draft()` reassigns `usage` on every iteration of its `for attempt in
   range(1, MAX_ATTEMPTS + 1)` loop. The row therefore describes the *terminal* provider call, not
   the creator's wait. For rows 453/454 these coincide — `created_at → redirected_at` minus
   `latency_ms` leaves 1.2s and 0.7s, so neither retried — but with `MAX_ATTEMPTS = 2` and
   `AI_REQUEST_TIMEOUT_SECONDS = 120` the worst case is a four-minute wait that the log would
   render as one ordinary call.
2. `usage.output_tokens` is `usageMetadata.candidatesTokenCount` only. For Gemini 3 models the
   default reasoning effort is `medium` and reasoning tokens are billed and spent but are not part
   of `candidatesTokenCount`. We never send a thinking configuration, so the single largest
   suspected contributor to latency is both unset and unmeasured.

## Goals / Non-Goals

**Goals:**

- Make the creator's wait attributable from the event log alone, without reading provider dashboards.
- Make reasoning effort a parameter we choose per environment, not a provider default we inherit.
- Keep a retried generation distinguishable from a single slow one.
- Change nothing a creator sees. This change buys the measurements that a later UX or tuning change
  will be argued from.

**Non-Goals:**

- Streaming responses and real progress reporting — the separate `ai-generation-streaming` change.
- Actually *choosing* a faster thinking level. This change makes the knob exist and the effect
  measurable; turning it is a follow-up decision made against data, not a guess made now.
- Backfilling the three existing rows. They have no such measurement; inventing one would poison
  the baseline the next comparison is drawn against.
- Changing the Anthropic provider's behavior.

## Decisions

### D1. Thinking level is a setting, sent as `generationConfig.thinkingConfig.thinkingLevel`

`AI_THINKING_LEVEL` (default `medium`, i.e. today's effective behavior) is read by the Gemini
provider and sent on every request. Verified against the current Gemini documentation: the REST
`generateContent` endpoint accepts `generationConfig.thinkingConfig`, and the documented levels are
`minimal`, `low`, `medium`, `high`.

Default `medium` rather than `low`: this change must not silently alter generation quality while
we are measuring. Shipping with the current effective value means the first deploy isolates the
measurement change; a subsequent env-var flip isolates the latency change. Two variables moving at
once would tell us nothing, which is the failure this whole change exists to end.

Empty string means "send no `thinkingConfig`" — an escape hatch if a future model rejects the field,
so a provider-side schema change is a config edit rather than a hotfix.

*Alternative considered:* hardcode `low` immediately. Rejected — it conflates the fix with the
experiment, and the quality cost on a constrained-JSON task is unknown.

### D2. Thinking tokens are derived defensively, and null means "not reported"

The provider reads reasoning usage as: `usageMetadata.thoughtsTokenCount` when present; otherwise
`totalTokenCount - promptTokenCount - candidatesTokenCount` when that difference is positive;
otherwise `None`.

The documented `usageMetadata` shape for a plain `generateContent` response carries only
`promptTokenCount`, `candidatesTokenCount` and `totalTokenCount`, and Google renames and adds fields
here faster than we deploy — the codebase already carries a scar about exactly that (`GEMINI_MODEL`
is an env var because models get retired and closed to new keys). Keying the feature to one field
name we cannot fully verify would make it silently record nothing. The subtraction is derivable from
fields the documentation does show, and it is correct whenever the provider accounts for reasoning
in the total.

`None`, never `0`: a provider that does not report reasoning usage and a provider that reasoned for
zero tokens are different facts, and averaging the second into a dashboard would understate the
first. The model field is nullable for the same reason.

*Alternative considered:* set `includeThoughts: true` and count the returned summaries. Rejected —
it pays for tokens and response bytes to obtain a number the metadata already carries, and thought
summaries are creator-invisible here.

### D3. `latency_ms` keeps its meaning; new fields carry the attempt set

Rather than redefine an existing column — which would make the three stored rows mean something
they were not measured as — the event gains:

- `attempts` — how many provider calls the set *started*. A call that raised before reporting usage
  still cost the creator their wait, so it counts; its duration is unknown, so it adds nothing to
  the sum. Understating elapsed is honest, inventing it is not.
- `total_latency_ms` — summed duration of every provider call that came back with usage.
- `thinking_tokens` — as per D2, summed across the calls that reported it, and `None` until at
  least one does.

`latency_ms` continues to mean the terminal call's own duration. A single-attempt generation has
`total_latency_ms == latency_ms` and `attempts == 1`, so the existing rows stay readable and the
new columns are additive rather than reinterpreting history.

Accumulation lives in `generate_survey_draft()`, which is the only place that knows the loop
happened; the provider stays a single-call abstraction and needs no notion of a retry.

*Alternative considered:* have `_finish()` diff `event.created_at` against `now()`. Rejected — that
measures queue wait and materialization too, which is a different (also useful) number, and it would
make the field mean something else again for the backfill command that writes historical rows.

### D4. Token accounting sums, provider/model take the terminal call's values

Across an attempt set the input, output and reasoning token counts are summed — that is what the
generation cost. Reasoning sums only over the calls that reported it and stays `None` until one
does, so D2's absent/zero distinction survives accumulation.
`provider` and `model` are taken from the terminal call, since they cannot differ within a set.
This keeps "what did this generation cost" answerable by reading one row, which is the same property
that made `creation_method` a breakdown rather than a join in the funnel work.

### D5. The new fields ride the existing `ai_draft_finished` event

`product_events.emit()` already sends `latency_ms`, `input_tokens` and `output_tokens` on
`ai_draft_finished`, guarded by a `is not None` check per field. The new fields join that same list,
so PostHog gains the breakdown with no new event and no new backfill path. `backfill_ai_events`
already copies whichever of these fields a row has, so historical rows simply carry fewer.

## Risks / Trade-offs

- **The subtraction in D2 could be wrong for a provider that excludes reasoning from
  `totalTokenCount`.** → It is guarded to a positive difference, so the wrong-direction case records
  `None` rather than a fabricated number. The `thoughtsTokenCount` branch is tried first, so a
  provider that reports the field directly never reaches the fallback.
- **`thinkingConfig` could be rejected by a future model, failing every generation.** → The empty-
  string escape hatch in D1 turns that into an env-var edit. The provider already surfaces the API's
  own error message rather than a guess, so the failure would be diagnosable from `error_detail`.
- **Two new nullable integer columns on a table that will grow per generation.** → Negligible; the
  table has three rows and grows at the rate creators generate drafts.
- **The measurement may exonerate thinking entirely** and point at provider-side variance we cannot
  control — the `503 high demand` fourteen minutes before the slow call is real evidence for that
  reading. → That is still a result: it would redirect effort to the streaming change and to
  retry-on-slow, and it is unreachable without these fields.

## Migration Plan

One additive migration, all columns nullable, no data migration and no backfill. Deploy order does
not matter: the code tolerates the columns being absent only in the sense that it never reads them
back, and the migration runs in Render's pre-deploy step as usual. Rollback is the reverse migration;
no other component reads the new fields.

Per the repository's deploy constraint, the commit adding the migration must not also touch
`preDeployCommand` — Render's pre-deploy has no shell and one merge fires two deploys.

## Open Questions

- Does `gemini-3.6-flash` actually report `thoughtsTokenCount` on `generateContent`? The fallback in
  D2 makes the answer non-blocking, and the first production row after deploy settles it. Worth
  confirming which branch fired before drawing conclusions from the numbers.
- Is `medium → low` acceptable for draft quality? Deliberately left open; it is the experiment this
  change enables, not a decision it makes.
