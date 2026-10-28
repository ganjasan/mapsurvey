## Context

`_emit_terminal_events` already sends `ai_draft_finished` with token counts to PostHog —
custom-schema events that product dashboards read but LLM Analytics does not. PostHog's
LLM product keys on `$ai_generation` / `$ai_feedback` with `$ai_*` properties and computes
cost per event from `$ai_model` + token counts. The PostHog snippet loads on all creator
surfaces (never on `/surveys/` or `/r/`), and the server-side client is configured in
`SurveyConfig` with the empty-key-means-off contract.

The boundary that governs everything here: PostHog measures **us** — the creator product.
The brief is the creator's project description, the draft is their survey content; neither
is ours to ship to an analytics vendor.

## Goals / Non-Goals

**Goals:**

- Cost, latency and error rate of the generator visible in PostHog's LLM Analytics with
  zero custom dashboards, agreeing with the measured batch ($0.067 / 10 drafts).
- A creator's verdict on a draft attached to the exact generation that produced it.
- Zero new failure modes for generation itself.

**Non-Goals:**

- Sending prompt or draft content — explicitly excluded, in both events.
- Replacing `ai_draft_finished` / `AIGenerationEvent` — the funnel events and the DB row
  remain the source of truth; PostHog LLM Analytics is a lens, not the ledger.
- PostHog Surveys — the native strip ties feedback to the trace id, needs no additional
  product enabled, and matches the editor's look. Surveys remain available later for
  broader questions.

## Decisions

### D1. `$ai_generation` is emitted server-side from `_emit_terminal_events`, once per attempt-set

Same place the funnel event fires, same never-raises contract, same distinct id (the
creator's pk — matching the browser snippet, which is what makes PostHog join the server
event to the person). One event per attempt-set, not per provider call: the row is the
unit our accounting speaks (attempts, summed tokens), and 19 events for 10 drafts would
double-count what the batch calls one generation each.

Trace id: `survey-draft-<event.pk>` — stable, unique, reconstructable from either side,
and within PostHog's documented character set for `$ai_trace_id`.

### D2. Reasoning tokens fold into `$ai_output_tokens`; the split rides separately

Gemini bills thinking at the output rate, so `$ai_output_tokens = output + thinking` is
what makes PostHog's computed cost equal the actual invoice. The measured batch is the
acceptance test: 12,669 in / 15,430 out+think must price out to ≈$0.067. The split is
preserved in a separate property for anyone asking "how much of this was reasoning";
`None` thinking contributes nothing rather than a fabricated zero, consistent with the
absent-not-zero rule the telemetry change established.

*Alternative considered:* `$ai_output_tokens` = visible output only. Rejected — PostHog
would systematically under-price every generation, and a cost dashboard that disagrees
with the invoice is worse than none.

### D3. Failures emit too, flagged, without their message

`$ai_is_error: true` plus the outcome slug (`provider_error`, `invalid_draft`, `error`).
The full `error_detail` stays in the DB row: provider messages have quoted fragments of
model output before ("unparseable model output: …"), and model output can quote the brief.
The slug gives PostHog its error rate; the detail stays home.

### D4. Feedback is a one-shot strip in the editor, keyed by the redirect

The success redirect becomes `/editor/surveys/<uuid>/?draft=<event id>`. The editor view
shows the strip only when the parameter names an `AIGenerationEvent` that belongs to the
requesting user AND whose `created_survey` is this survey — an unvalidated id must not
conjure UI, and the check is one indexed lookup. The strip renders only when the PostHog
key is configured (no snippet, no capture, no strip).

Client-side `posthog.capture('$ai_feedback', {...})` carries the trace id, `rating`
(`up`/`down`) and an optional freeform comment. The comment IS creator-authored content —
but it is their opinion about *our* feature, addressed to us, which is exactly the
category PostHog holds. Submitting or dismissing hides the strip and stamps
`localStorage` so a page reload does not re-ask; the server-side one-shot is the `?draft`
parameter itself, which only the generation redirect produces.

*Alternative considered:* a PostHog Survey targeted at `ai_draft_opened`. Rejected for
v1 — it cannot carry the trace id without custom wiring anyway, and it requires enabling
`surveys_opt_in` project-wide.

## Risks / Trade-offs

- **PostHog may not price `gemini-3.6-flash`** (models churn faster than price lists). →
  Token counts and latency still land; cost shows blank rather than wrong. Verify against
  the batch numbers after the first production events and, if unpriced, the model name is
  the thing to check first.
- **The strip is one more thing on a page the creator just arrived at.** → Single
  dismissible line under the editor toolbar, shown once per draft, never for manual
  surveys.
- **A second capture call per generation.** → Same fire-and-forget client the funnel
  events use; a PostHog outage already cannot fail a generation.

## Migration Plan

No migration, no model change, no new settings. Deploy order irrelevant. Rollback is a
revert; unsetting `POSTHOG_PROJECT_KEY` was and remains the master off-switch for every
capture path at once.

## Open Questions

- None blocking. Whether to add a PostHog Survey for richer periodic feedback is a later
  product call once the strip's response rate is known.
