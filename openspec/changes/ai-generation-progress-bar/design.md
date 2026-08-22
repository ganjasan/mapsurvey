## Context

Streaming already delivers real counts: `DraftProgress` counts questions and sections as
they close, the worker publishes them to `AIGenerationEvent`, and the status endpoint
returns a fragment only when they advance, swapped out-of-band so the card never
re-renders. Production runs with streaming off; previews run with it on. The card shows
rotating quips because, at the time it was written, there was nothing honest to show.

There is now. What this change decides is how to give the counts a bar shape without the
bar lying, and it does so under a user decision made explicitly and twice: a proper
progress bar, prioritised over the flavour text.

Measured reality the design leans on: drafts land at 3 sections / 8–9 questions; at
thinking `low` the whole generation is ~12s with the first question at ~4–6s; at `medium`
~36s with a long silent reasoning stretch first.

## Goals / Non-Goals

**Goals:**

- A bar that moves when the draft moves, visibly distinct between "model is thinking" and
  "draft is being written".
- Zero new data plumbing — everything is derived from counts the endpoint already serves.
- Streaming on in production, with the existing kill switch untouched.

**Non-Goals:**

- A percentage label or an ETA. The bar communicates motion and rough position; the counter
  next to it states the only exact facts we have. Printing "62%" would claim a precision
  the denominator does not possess.
- Removing the polling architecture. 2s polls at 12–36s waits are fine; SSE to the browser
  remains out of scope.
- Changing quota, retry, or any generation semantics.

## Decisions

### D1. Two-phase bar: indeterminate stripe → determinate fill

Before the first question closes, the bar shows an animated indeterminate stripe — the
established idiom for "working, no measurable progress yet", and true here: the model is
reasoning. From the first question on, it becomes a determinate fill.

The phase switch is driven by the same fragment that already appears only when a count
advances, so the client needs no logic: the placeholder renders the stripe, the first
fragment replaces it with a fill.

### D2. Fill = questions drafted against a calibrated expectation, capped at 90%

`fill = min(90, round(questions * 90 / EXPECTED_QUESTIONS))`, with
`EXPECTED_QUESTIONS = 8` — the median of recorded drafts. On success the redirect fires
and the bar never needs to show 100; the cap means a draft that runs long parks at 90
rather than pinning at full and then visibly stalling, which is the classic progress-bar
lie this design is built to avoid.

Server-side, in the fragment context: the client stays dumb, and the constant lives next
to a comment naming it a display calibration, revisitable against
`AIGenerationEvent.questions_drafted` as rows accumulate.

*Alternative considered:* deriving the expectation per-request from the brief. Rejected —
the brief does not state a question count, and inventing a mapping from prose to a number
is a worse guess wearing more code.

*Alternative considered:* asymptotic fill (`1 - e^{-kq}`). Rejected — it decelerates in a
way that reads as the generation slowing down, which is false; linear-to-cap tracks the
actual arrival rhythm.

### D3. The quips are removed, not demoted

The user's direction was explicit that the flavour text is not the experience they want.
The card keeps its title, the bar, the counter caption, and the leave-the-page note. The
no-fabricated-stages rule survives intact: everything shown is either real counts, a real
fill derived from them, or an honest "no measurable progress yet" stripe.

### D4. Production streaming flips in render.yaml, not in the dashboard

The split (`value` / `previewValue`) was built as the re-enablement mechanism, so the flip
is a one-line diff with history, review, and a revert path — unlike a dashboard edit,
which is invisible in the repo. The kill switch semantics stay: `false` in the dashboard
still wins for an emergency, and previews stay `true` regardless.

## Risks / Trade-offs

- **A short draft (5 questions) jumps 90% in five steps; a long one (14) crawls past 90
  early.** → The cap and the counter absorb both: the bar is motion, the numbers are
  truth. The calibration constant is one line to tune.
- **Streaming returns to production carrying its history.** → Its two production failures
  are each closed by a specific bound with a test naming them, the stall dies in 30s into
  a silent retry, and the kill switch is one dashboard edit. This is the accepted residual
  risk of the user's call, made with that history known.
- **At `low`, the whole bar lives ~8 seconds.** → Fine: a fast bar is a good problem, and
  `medium`-style briefs and future providers keep the indeterminate phase meaningful.

## Migration Plan

Template + CSS + one view context value + one render.yaml line. No migration, no model
change. Rollback is a revert; emergency rollback of streaming alone is the dashboard kill
switch.

## Open Questions

- None blocking. Recalibrating `EXPECTED_QUESTIONS` from telemetry once a few dozen real
  drafts exist is follow-up hygiene, not a decision this change needs.
