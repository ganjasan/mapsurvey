# AI-assisted response triage (relevance, spam, duplicates)

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: pro-tier
**Tier**: **Pro**
**Created**: 2026-07-31
**Related**: [AI analytics over survey responses](feature-ai-analytics.md) (#92), [AI survey creator agent](idea-ai-survey-creator-chat-agent.md) (#15), [Public results map](feature-public-results-map.md) (#27)

## Description

Let the survey owner review incoming responses with model assistance before they reach
analysis or a public results map: flag off-topic entries, obvious spam, duplicates, and
geometries placed outside the study area — and let the owner accept or reject each flag.

This is the step *before* [AI analytics](feature-ai-analytics.md). Analytics summarises
what was collected; triage decides what counts as collected at all. A consultancy
publishing results under its own name cannot put an unfiltered pile in front of a
municipal client.

## Evidence

- **Asked for, unprompted, by a real buyer.** Marcus Wildner (ThINK Jena, climate
  consultancy) on the call of 2026-07-31: can AI filter out irrelevant answers? He raised
  it himself, before any feature was pitched to him — and he had not engaged with survey
  *building* at all. The interest is in getting from raw responses to usable material,
  not in the editor.
- Same call: he had never heard of MCP. An "attach your own AI client" story does not
  land with this persona; the assistance has to live in the product.
- Public results maps make this blocking rather than nice-to-have: the moment responses
  are published, an unmoderated abusive or off-topic entry is the client's problem, in
  public, under the consultancy's name.

## Scope Sketch

- **Flag, never auto-delete.** Every flag is a suggestion with a reason, reversible, and
  the original response is never destroyed. A silently dropped legitimate answer is worse
  than a visible bad one — and in a public participation process it is politically
  dangerous: "the tool deleted my submission" is a story no municipality wants.
- Flag categories: off-topic for this survey, spam/nonsense, duplicate of an existing
  response, geometry outside the study area, abusive language.
- **Geometry-outside-area needs no model** — it is a spatial predicate against the survey
  boundary. Build that first: it is cheap, deterministic, and probably the most common
  real case.
- Bulk accept/reject in the response list; a filter for "flagged" in analytics and export.
- Audit trail of who accepted or rejected which flag — see
  [Audit trail](feature-audit-trail.md).

## Open questions

- Does a rejected response stay out of the GeoJSON export, or is it exported with a
  `flagged` property? Leaning toward exporting the flag as a property: the researcher
  decides, we do not silently shrink their dataset.
- Free-text moderation touches respondent-authored content going to a model API — needs
  the same privacy notice as the AI agent, and interacts with EU hosting
  ([#35](feature-eu-data-hosting-option.md)). A German client requiring German hosting
  will ask where the moderation model runs. Do not assume the answer is acceptable.
