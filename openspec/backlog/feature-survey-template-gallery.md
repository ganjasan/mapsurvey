# Survey template gallery (onboarding / activation)

**Type**: feature
**Priority**: medium
**Area**: frontend
**Epic**: growth
**Created**: 2026-06-10

## Description

Offer new registrants a gallery of ready-made survey templates based on the use cases that already work on the platform, so they reach a published, response-collecting survey fast instead of starting from a blank editor. Attacks the activation leak, not acquisition: many high-value signups register and never return.

## Evidence (from 2026-06-10 analysis)

- Large graveyard of dormant high-value registrations that never built a survey: Columbia, CNR (Italy), Michael Baker International, RMIT, Univ. of York, Alexandria Univ., and many "0 surveys / never returned" accounts.
- Acquiring more of the same and losing them is a leaky bucket — activation has to be fixed alongside acquisition.
- Proven, recurring use-case clusters to seed templates from:
  - Urban mobility / transport (Lyon, Ivry, Berlin Senate)
  - Walkability / sidewalk audit (FTSPK class)
  - Participatory / community asset mapping
  - Citizen science (snowdrop mapping, "find cherries", orca/otter sightings)
  - School route safety (Japanese PTA)
  - Tourism mapping (Hamina)

## Three templates already exist (2026-07-31)

Built by hand for the ThINK Jena conversation, import-tested, EN base + DE, in
`user_surveys/`. They are curated survey definitions in exactly the format this feature
would serve, so the seed set is partly done:

- `hitzekarte_klimaanpassung_demo` — **heat action plan / Klimaanpassung**: residents map
  unbearably hot places (typed sub-questions: kind of place, time of day, what is
  missing, severity, photo), cool refuges with an accessibility question, routes without
  shade, hot/cool areas, then cooling ideas in 8 categories, plus a vulnerability block.
  Its question set was revised against the PPGIS literature — see
  `docs/research/ppgis-heat-participation.md`.
- `waermeplanung_quedlinburg_demo` — **kommunale Wärmeplanung**: building point carrying
  8 sub-questions so attributes land in GeoJSON `properties`.
- `ideenkarte_klimaschutz_demo` — **topic-neutral idea collection** in 8 categories,
  point + line + polygon.

Note what this implies for sequencing: templates are the *sales* artefact too. Building a
demo for the prospect's own use case took an afternoon and was the main thing to send
after the call. If that is repeatable, the gallery is not only an activation feature — it
is the thing the founder-led sales motion consumes weekly.

Climate adaptation is also a defensible vertical: German municipalities must produce
Klimaanpassungskonzepte under KAnG §8 by 2027, and several cities already run
"Karte der kühlen Orte" participation projects (Nürnberg, Dortmund, Regensburg, Augsburg).

## Scope

- Template = pre-built sections + questions (incl. geo question types) + sensible defaults, cloneable into the user's account in one click.
- Surface in onboarding right after registration and as a "New survey from template" option in the editor.
- Seed set: 6–8 templates from the proven clusters above, multilingual where relevant.
- Ties to [coursework channel](idea-coursework-education-channel.md) — assignment templates (walkability audit, accessibility mapping) live here too.

## Notes

- Reuses existing survey serialization/import machinery (templates are essentially curated importable survey definitions).
- The user-outreach campaign is the cheapest way to learn *why* dormant users bounced — feed those findings into which templates to build first.
- Distinct from [answer choice templates](feature-answer-choice-templates.md) (that's reusable answer option sets, not whole-survey templates).
- **Role in the activation stack** (see [growth epic](epics/growth.md)): this is the *cheapest, lowest-risk* layer and doubles as (a) the seed/few-shot library for the [AI survey-creator agent](idea-ai-survey-creator-chat-agent.md), and (b) the deterministic fallback when AI generation fails or is cost-capped. It is NOT a competitor to onboarding/AI — ship it first as the measured baseline, then layer [interactive onboarding](idea-interactive-onboarding.md) and the AI agent on top. Likely converts worse than guided onboarding on its own (a clone still leaves a near-blank editor and doesn't drive the publish/share step) — but its build cost is days, and it de-risks the rest.
