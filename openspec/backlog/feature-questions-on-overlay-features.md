# Ask questions about the creator's own map objects (rate, vote, comment)

**Type**: feature
**Priority**: **very high**
**Area**: backend
**Created**: 2026-08-26

## Description

Today a respondent can only answer with geometry they draw themselves. There is no way to ask
"what do you think of *this*" about an object the creator put on the map. That rules out the
whole class of consultation the market is actually built around: rate every tram stop for
accessibility, pick between three route variants, comment on each of the six proposed sites.

A creator attaches a question to a reference overlay layer; the respondent answers it **once
per feature**, on as many features as they care about. Answers store a reference to the
feature, not a geometry the respondent drew.

Seen in PARTIMAP's demo twice, in two different shapes:
[stars per metro station](../../docs/marketing/competitors/partimap/06-per-feature-question.jpg)
and [👍/👎 between route alternatives](../../docs/marketing/competitors/partimap/08-alternatives-vote.jpg).

## Why this one and not the others

Two independent confirmations, from opposite directions:

- [Ideenkarte](../../docs/marketing/competitors/) — the first confirmed incumbent we are
  being measured against (ThINK Jena) — has like/dislike voting, and it sits in our recorded
  gap list against them alongside the public live map.
- Marcus Wildner (ThINK) asked about exactly this territory on the 2026-07-31 call.

Everything else on the PARTIMAP list makes an existing scenario nicer. This one opens a
scenario we cannot serve at all today, and it is the scenario municipalities buy.

## What it needs

- **Model**: an answer that points at an overlay feature. `Answer` today is keyed to a
  `Question` and holds a value or a geometry; this needs a stable feature reference
  (`key_field` from FD-1 gives the identity) plus a uniqueness rule of one answer per
  (session, question, feature). Do not model it as a sub-question of a geo answer — the
  respondent did not create the parent object, the creator did, and
  [architecture_subquestions_geojson](../../CLAUDE.md) reasoning does not apply.
- **Question types on a feature**: rating (stars) and 👍/👎 first, since those are the two
  observed; then `choice` and free text. 👍/👎 may be worth its own input type rather than a
  two-option choice — it is a distinct affordance and it is what the competitor gap names.
- **Which features are askable**: all of them, or a subset the creator marks. Alternatives
  (three route variants) and asset inventories (40 stations) look the same to the model but
  read very differently in the UI.
- **Progress and required-ness**: "rate the stations" cannot mean "rate all 40 stations or
  you may not continue". Needs an explicit minimum (0 by default) rather than inheriting the
  ordinary required flag.
- **Already-answered state**: PARTIMAP greys out what you rated. Cheap, and it is the only
  thing that makes a 40-feature list finishable.
- **Export**: these answers must land in the ZIP. They are not geometry the respondent drew,
  so they belong in the CSV keyed by feature id — and the GeoJSON of the creator's layer,
  enriched with aggregates, is the artifact a planner actually wants.
- Anonymity: aggregates per feature are a k-anonymity surface exactly like the public results
  page. Reuse the existing masking rather than inventing a second rule.

## Notes

- Depends on [#151](feature-overlay-feature-browser.md) for the respondent to find the
  feature at all. #151 without this is still useful (presentation); this without #151 is
  unusable past a handful of features.
- Pairs with [#153](feature-inline-results-step.md): the aggregate per feature is what gets
  printed on the marker.
- Distinct from [public results map](feature-public-results-map.md) (#10), which publishes
  what respondents drew. This publishes what respondents thought about what the creator drew.
- Epic: community-engagement
