# AI activation analytics — hypothesis instrument for the onboarding bet

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: survey-analytics
**Created**: 2026-08-14
**Related**: [AI survey generator](idea-ai-survey-creator-chat-agent.md) (shipped the server-side half), [Funnel monitoring](feature-funnel-monitoring.md)

## Description

The AI onboarding hypothesis — *"an AI-drafted first survey significantly raises
registration → first-published-survey conversion"* — needs a measurement instrument, not
just a feeling. The server-side half already ships with the generator
(`AIGenerationEvent`: brief text, generated blob snapshot, tokens/latency, outcome,
`last_polled_at`/`redirected_at` for waited-vs-left). This item is the analysis and
observation half.

## Scope Sketch

- **Staff dashboard section** ("AI activation") on the existing funnel dashboard
  (`survey/funnel.py` conventions): briefs submitted → generated → waited/left →
  draft opened → edited → published → got responses. Cohort split: AI-origin vs manual
  surveys (via the `created_survey` back-reference — no schema change needed).
- **Generated-vs-published diff**: compute manual-repair metrics from
  `AIGenerationEvent.generated_blob` against the survey's current structure (questions
  deleted / renamed / added). The honest draft-quality metric.
- **Respondent-side quality**: answer-rate and completion for AI-origin surveys vs
  manual ones — reuses existing response analytics with an origin filter.
- **Client events** (second iteration): "panel seen", "brief focused but never
  generated", "chose Create empty despite panel" — via the existing track-event
  endpoint pattern.
- **PostHog (self-hosted) or fork-friendly alternative** for session replay of
  `/editor/*` and funnels-by-clicks. Constraints from the 2026-08-14 discussion:
  forkability matters (open-source, modifiable), so PostHog hobby self-host
  (MIT core: replay + basic flags; experiments are proprietary/ee — pair with
  **GrowthBook** for A/B math over our own Postgres) or a lighter Umami+GrowthBook
  stack. Never on respondent pages; never send brief text to third parties; join by
  `distinct_id = user.id`.

## Notes

- At current traffic (~10–20 registrations/week) a randomized A/B lacks power; the
  instrument should support before/after cohort comparison first, with the flag
  infrastructure ready for A/B when traffic allows.
- Define the activation metric BEFORE reading the data: share of registrations
  publishing their first survey within 14 days.
- Qualitative loop: reading real briefs against their outcomes (already possible in the
  `AIGenerationEvent` admin) is the highest-signal activity at this scale.
