# Survey insights layer — automated read-out of how a survey performed

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: survey-analytics
**Created**: 2026-08-16

## Description

The Performance tab already computes the numbers (per-section views/submits/drop_rate,
completion rate, referrer/device/language splits, time on section). What it does not do
is say what the numbers mean. The Pszów survey (id 379) made the gap concrete: the
dashboard shows twelve rows of drop rates; the hand-written read-out said "your entire
loss is one boundary — eight intro questions before the first map — and the drawing tool
is fine, because the funnel is non-monotonic past that point." The second sentence is
what a creator acts on, and every part of it was computed from data we already collect.

This is also the productised half of the service-model hypothesis: every lead builds a
survey and then cannot make sense of what happened. An automated read-out is the "help
them understand it" service without the consulting hours.

## Scope Sketch

Two tiers, strictly layered:

- **Tier 1 — deterministic detectors, no AI.** Rules over existing `SurveyEvent` +
  `Answer` data, each emitting a typed finding:
  - *Drop concentration*: one section transition loses more than the rest of the funnel
    combined ("136 → 76 at intro→map").
  - *Non-monotonic funnel after the drop point*: respondents skip a question and
    continue → the problem is the question, not the widget.
  - *Question underperformance vs peers*: same input_type, materially lower response
    rate → wording problem ("magic wand" 71 vs "where do you wait" 49).
  - *Structure smells*: N non-spatial screens before the first geo question; required
    free-text; sections with zero answers.
  - *Completion depth distribution*: opened / answered intro only / drew geometry /
    completed (the four honest numbers, not just completion_rate).
  - *Cohort contrast*: spike days vs tail days (zero-answer share differs by source of
    traffic).
- **Tier 2 — optional narrative via the existing Gemini integration.** Input is Tier 1
  findings only, never raw data — the model phrases and prioritises, it does not
  discover. Output: a short "what I would change" paragraph in the survey's language.
- **Delivery**: an Insights panel on the analytics dashboard; later a creator email
  digest ("+N responses this week, biggest loss at X") — the digest doubles as the only
  re-engagement channel for dormant authors.

## Guardrails

- Creator-facing only. Findings never appear on `/r/<slug>/`.
- Tier 1 must stand alone: with AI disabled per workspace (see #92's subprocessor
  concerns) the detector findings still render as plain statements.
- Minimum-data thresholds per detector — a funnel over 5 sessions produces noise, not
  insight; below threshold say "not enough responses yet", never a false finding.

## Dependencies / Related

- [AI analytics over survey responses](feature-ai-analytics.md) (#92) — analyses answer
  *content*; this analyses survey *performance*. Same Gemini plumbing for Tier 2,
  same opt-in and subprocessor story.
- Pro-tier candidate: raw numbers free, insights and digest paid — fits the
  project-line-item model.
- Origin: hand-made read-out for the Pszów survey, offered to its creator 2026-08-16
  (`docs/marketing/user-outreach/patricio22/`). His reply is the first template test.
