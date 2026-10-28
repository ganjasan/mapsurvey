## Context

The overlay went quips → quips + counter → bar + counter → bare indeterminate bar, each
step locally justified, and the end state is worse than the start. Two user directives
close the loop: the quips were better, and the bar irritates — remove it. The reference
is Claude Code's own status line: `✻ Frosting… (26s · …)` — personality plus a live
elapsed fact, no fabricated position.

## Goals / Non-Goals

**Goals:**

- A wait that feels alive and intentional with zero fabricated measurement.
- Real counts still win when they exist (streamed previews), as plain text.
- Net code reduction: the bar, its CSS, its fill math and its calibration constant go.

**Non-Goals:**

- Any percent, fill, or ETA. Removed, not redesigned.
- Touching generation semantics, retries, or telemetry.

## Decisions

### D1. Spinner + quip + elapsed, one line

The card already has a spinner. The quip line returns beneath the title with the same
rotator (restored from history), and the elapsed counter renders inline after the quip:
"Sharpening the map pins… (14s)". The counter ticks client-side from overlay mount —
elapsed wall-clock is the one number a wait screen can show without measuring the
backend, and it doubles as the "not frozen" signal the bar was failing to be.

### D2. Counts replace the quip line's slot via the existing OOB fragment

The `#gen-progress` element stays as the swap target; empty in the placeholder, and the
fragment fills it with the caption only ("4 questions · 2 sections drafted"). The quip
line is a separate element that keeps rotating and ticking either way — flavour and fact
coexist, nothing is hidden by data arriving.

### D3. `EXPECTED_QUESTIONS` and the fill leave the codebase

The calibration constant existed solely to denominate the bar. With no bar there is
nothing to calibrate; keeping it "in case" would be dead weight with an authoritative-
looking comment. The view passes counts only; the no-percentage-label test survives as
the guard that no percentage sneaks back.

## Risks / Trade-offs

- **Third UX change to this card in one day.** → Each was user-directed, and this one
  deletes more than it adds; the card ends simpler than it began.
- **A long retry-laden wait shows only a growing timer.** → That is honest, and the
  "usually takes under a minute / you can leave" note already covers expectations.

## Migration Plan

Templates, CSS, one view context, tests. No migration, no settings. Rollback is a revert.

## Open Questions

None.
