## Why

The generation wait currently shows rotating flavour text, and in production not even the
progress counter, because streaming is off there. The user's direction, stated twice and
standing: creators should see a proper progress bar, not quips. The original objection —
a bar needs a denominator and we did not know one — is now answerable with data instead of
a guess: real drafts land at 3 sections and 8–9 questions, and the event log records every
generation's counts, so a calibrated expectation exists and can be revisited as telemetry
accumulates.

The prerequisite also holds now: streaming is proven on a stand (counter moving from the
first question, 12s end-to-end at `low`), stalls and truncations are bounded and retried,
and the kill switch stays. What remains is turning it on for production and giving the
counts a visual shape.

## What Changes

- **The waiting card gains a real progress bar.** Indeterminate (animated) while the model
  is still reasoning and nothing has been drafted; determinate once the first question
  closes, filling proportionally to questions drafted against a calibrated expectation,
  capped below full until the draft actually lands. The existing question/section counter
  stays as the bar's caption — the bar shows motion, the numbers say what it means.
- **The quips go.** The bar and counter replace the rotating flavour text as the primary
  signal; the card keeps its title and the "you can leave this page" note.
- **The expectation is a named constant calibrated from telemetry** (`8` questions today,
  from the recorded drafts), documented as a display calibration — not a promise — and
  trivially updatable as `AIGenerationEvent` accumulates rows.
- **Streaming turns on in production** (`render.yaml` value flip for web and celery). The
  preview/production split stays in place as the mechanism; this change flips the
  production side now that a stand has proven the bounds.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-survey-generation`: the **Asynchronous generation with status polling** requirement
  changes — the pending state SHALL present a progress bar driven by the drafted counts
  (indeterminate before the first question, determinate and capped after), replacing
  flavour text as the primary wait signal.

## Impact

- `survey/templates/editor/partials/generation_status.html` — bar markup, quip removal.
- `survey/templates/editor/partials/generation_progress.html` — fragment carries the bar
  fill; width computed server-side so the client stays dumb.
- `survey/templates/editor/partials/_generation_overlay_css.html` — bar styles, both modes.
- `survey/editor_views.py` — fragment context gains the computed fill percentage.
- `render.yaml` — `AI_STREAMING_ENABLED` production value flips to `"true"`.
- No model changes, no migration; the counts and polling contract are already in place.
