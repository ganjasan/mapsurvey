## Context

`PerformanceAnalyticsService.get_funnel()` (origin/master) already counts distinct sessions per
section and clamps `dropped` at zero with a comment that a conditional branch can make a later
section more visited than an earlier one. The UI does not know which steps are conditional, so
the clamp hides the symptom on the successor while the branch itself still reads as a loss.

Rules are `SurveySection.visibility_rule = {"question_code", "choice_codes"}`, any-of match on an
earlier `choice`/`multichoice` answer; `survey/visibility.py` owns verdicts (`_rule_verdict`,
`describe_rule`). Answers store the selected codes in `Answer.selected_choices` (JSON list).
Events carry `section_name`, so the funnel already keys everything by section name and reads
sections from the canonical survey only, while events/answers come from every version in scope.

Mockup: `funnel-conditional.mockup.html` in this folder (desktop, phone, loss-inside-branch).

## Goals / Non-Goals

**Goals:**
- Never report a rule-skipped respondent as dropped.
- Drop rate of a conditional step relative to who was eligible.
- Successor of a branch compared with the last unconditional step.
- Conditional steps recognisable without reading the numbers; broken rules flagged.

**Non-Goals:**
- Question-level visibility rules (they do not change which sections are viewed).
- Rule cascades across sections (a section rule whose controller is itself hidden) — the
  eligibility count uses the answer alone; a hidden controller has no answer, so it lands in
  "skipped", which is the truthful outcome.
- Any change to the events emitted by the respondent page.

## Decisions

**D1 — Eligibility from answers, not from events.** `eligible(section)` = distinct sessions in
scope that (a) reached the baseline step and (b) have an `Answer` on the controller question
whose `selected_choices` intersects `choice_codes`. Then `skipped = baseline_reached − eligible`
and `dropped = max(eligible − reached, 0)`. Alternative: `skipped = baseline − reached`, from
events only — simpler, but it cannot separate "skipped" from "eligible and left", and the whole
point is that separation. Answers are read by `question__code` across the version scope, the same
key the engine uses, so an older version's respondents count as long as the code survived.

**D2 — Baseline = last unconditional step.** Walking sections in order, `prev_reached` is updated
only by unconditional steps (and by broken-rule steps, which everyone sees). A conditional step
compares with the baseline for `skipped`; the step after it compares with the same baseline for
`dropped` and the label says "since step N" whenever N is not the immediately preceding step.
Alternative: baseline = union of reached sets of all steps since the last unconditional one —
more exact when consecutive branches partition the audience, but unexplainable in a caption.

**D3 — Bar scale unchanged.** Height stays `reached / session_starts`. The skipped share is drawn
as a light band directly above the fill (height `skipped / session_starts`), inside the hatched
remainder. Keeps the chart monotone-readable; the band tells the story without a second axis.

**D4 — Badge reuses `describe_rule`.** Label "Shown when <controller name> = <options>" from the
same helper the editor uses; truncated with the full text in `title`. Broken rule → the editor's
warning badge with its `reason`, and the step is treated as unconditional (fail open).

**D5 — Payload additive.** New keys per step: `conditional` (bool), `rule_label`, `rule_broken`,
`rule_reason`, `eligible`, `skipped`, `skipped_pct` (of session starts, for the band),
`eligible_pct` (reached of eligible), `baseline_step`. Existing keys keep their meaning;
`dropped_pct` for a conditional step is now relative to `eligible`. Nothing consumes `funnel_json`
beyond the template today, so no client code changes.

## Risks / Trade-offs

- [Answers of a session that reached the baseline but never submitted the controller's section]
  → they have no answer, so they count as skipped, not dropped. Acceptable: they *were* counted as
  dropped on the baseline step already; double-counting them here would be worse.
- [Controller question deleted or code changed in a later version] → `_rule_verdict` reports
  broken; step renders as unconditional with the warning badge. No crash, no silent zero.
- [Extra queries per conditional section] → one `values_list` over `Answer` filtered by
  `question__code` and session scope per conditional section; editor-render scale only.
- [Small samples] → the existing <20-sessions notice already suppresses percentages; the new
  "of eligible" percentage follows the same gate.
