## Why

With production streaming off, the waiting card degraded to a bare indeterminate bar for
the whole wait. The user's verdict came in two parts: even the quips were better — and
the bar itself is irritating, remove it entirely. The pattern worth borrowing is Claude
Code's own status line: a spinner, a whimsical word, a live elapsed counter, and nothing
pretending to be a measurement.

## What Changes

- **The progress bar is removed entirely** — both the indeterminate sweep and the
  determinate fill, with its server-computed percentage and calibration constant.
- **The waiting card becomes spinner + rotating quip + live elapsed counter** (`(14s)`,
  ticking client-side). Elapsed time is a fact and the strongest honest "not frozen"
  signal available without measuring anything.
- **Real progress, when streaming supplies it, is text**: the out-of-band fragment
  carries the drafted-counts caption ("4 questions · 2 sections drafted") in place of
  the quip line. Data still beats flavour when data exists — it just no longer wears a
  bar.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-survey-generation`: the waiting-card clause of **Asynchronous generation with
  status polling** — the bar requirement is replaced by quip-plus-elapsed, with the
  drafted-counts caption when counts exist.

## Impact

- `survey/templates/editor/partials/generation_status.html` — bar out; quips, elapsed
  counter and rotator in.
- `survey/templates/editor/partials/generation_progress.html` — caption only, no fill.
- `survey/templates/editor/partials/_generation_overlay_css.html` — bar styles out, quip
  styles back.
- `survey/editor_views.py` — `EXPECTED_QUESTIONS` and the fill computation removed.
- Waiting-card and fill tests updated to the new contract.
