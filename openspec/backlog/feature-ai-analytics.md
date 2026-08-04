# AI analytics over survey responses

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

Turn collected responses into the thing the buyer actually owes their client: findings.
A consultancy running a participation project does not need charts, it needs a section of
a report. Free text answers and mapped geometries are exactly the material that is
expensive to analyse by hand and cheap to analyse with a model.

## Scope Sketch

- **Free-text coding**: cluster open answers into recurring themes, name the themes,
  count them, and link each theme back to the individual responses that produced it.
  Never present a theme the user cannot drill into — an unverifiable summary is worthless
  in a report that gets published.
- **Spatial summarisation**: describe where the clusters are ("most heat-pump objections
  come from the Altstadt blocks"), using the geometries plus their sub-question
  attributes.
- **Cross-cutting**: differences between respondent segments where the survey collected
  segmentation questions.
- **Draft report section**: exportable narrative with the numbers and a map figure,
  in the survey's language.
- Cost control: per-workspace usage accounting; this has real marginal cost, which is
  itself the reason it cannot sit in Free.

## Guardrails

- Every generated claim must carry its supporting response IDs. Participation results
  end up in council documents; a hallucinated finding is a liability for the client and
  for us.
- Personal data in free text goes to a model provider — this must be declared in the
  subprocessor list and be switchable off per workspace, or it will block exactly the
  German public-sector deals the Pro tier is built for. See
  [DPA / AVV compliance pack](feature-dpa-compliance-pack.md) (#88).
- Offer it as opt-in per survey, not silently on.

## Dependencies / Related

- [AI survey-creator agent](idea-ai-survey-creator-chat-agent.md) (#15) — same model
  plumbing, opposite end of the lifecycle; build the shared infrastructure once.
- NVivo is the reference for what qualitative practitioners expect (coding, summaries,
  word clouds, mixed methods).
