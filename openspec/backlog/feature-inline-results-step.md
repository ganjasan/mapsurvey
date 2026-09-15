# Show respondents the results so far, as a step inside the survey

**Type**: feature
**Priority**: high
**Area**: backend
**Created**: 2026-08-26

## Description

A section whose content is not questions but the aggregated answers collected so far —
"here is what your neighbours said, now continue". PARTIMAP puts one after each block of
questions and says so on the preceding slide: *before proceeding, we can display the
respondents the results*
([screenshot](../../docs/marketing/competitors/partimap/02-inline-results.jpg)). On map
slides the same idea is drawn on the map itself: the average rating printed on each marker,
and a sorted league table beside it
([screenshot](../../docs/marketing/competitors/partimap/07-ratings-on-map.jpg)).

## Why it is cheap for us

The whole engine already exists and is shipped: `PublicResultsService`, `render_page_data`,
the block model, the 60s live cache, k-anonymity masking with `K=3`, the clean-sessions
definition that excludes `not_approved`/`on_hold`. What is missing is a way to render those
blocks *inside a survey section* instead of only at `/r/<slug>/`, and a chart type that draws
an aggregate onto a map feature.

## What it needs

- A section (or block) type "results", pointing at a subset of the existing results blocks.
- Reuse the aggregation path unchanged — including masking. A respondent mid-survey is a less
  trusted reader than a visitor to a published results page, never a more trusted one, so the
  privacy rules cannot be loosened here. Individual free-text answers stay unpublished.
- Decide what "so far" means against the cache: the 60s live window is fine, but a respondent
  who just answered and does not see their own answer reflected will read it as a bug. Either
  say "updated every minute" in the UI or exclude the current session from the copy.
- Aggregates painted on map features (needs [#152](feature-questions-on-overlay-features.md)
  for anything to aggregate).
- A floor before anything renders. [Live results projection](feature-live-results-projection.md)
  (#31) already carries this requirement — a minimum response threshold so nobody draws a
  conclusion from n=4. Same rule, same reason, and here it doubles as the k-anonymity guard.

## Notes

- Second-order benefit worth naming: it puts the results surface in front of creators who
  never discover `/r/<slug>/`. That is the mechanism behind
  [[lesson-preview-link-registration-trap]] — creators share whatever URL the product showed
  them. If the results page is part of the flow they build, they stop sharing the editor
  preview link and manufacturing fake registrations.
- Related: [auto-draft the public results page on publish](feature-auto-draft-public-results-page.md)
  (#130) attacks the same discovery problem from the creator's side. These two together are
  the whole answer; either alone is half.
- Not to be confused with [live results projection](feature-live-results-projection.md) (#31),
  which is a facilitator-facing presentation mode for a room with a projector.
- Epic: community-engagement
