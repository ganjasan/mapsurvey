## Why

The public results page draws every answer's geometry at its real location. A pin at a front door
says where a respondent lives and what they said — the re-identification risk k-anonymity exists
for — and the same map reaches Site results blocks unchanged. k-anonymity itself lives inside
`PublicResultsService`, so every new public surface (Site blocks today, report embeds and
open-data pages next) would need its own copy. The owner decided on 2026-11-14 (ADR-001 §6.3):
exact numbers stay inside the workspace (API, MCP, Responses), k-anonymity applies wherever data
leaves it, and public maps show cells with cells under K hidden instead of points. This is the
first half of #666 (ADR-001 move 2); the `data.features` consolidation follows in its own change.

## What Changes

- New `data.aggregate`: `mask(count, k)` (the "<K" display), and `grid(members, k, …)` — the
  spray density grid generalised to every geometry: a point counts in its cell, a spray cloud in
  every cell holding one of its dots, a line or polygon in every cell it touches; each cell counts
  DISTINCT respondents and cells under K are omitted.
- **BREAKING (public)**: map blocks of point, line and polygon questions on `/r/` and in Site
  results blocks publish a grid of cells instead of the answers' geometries. A cell's popup shows
  the number of respondents and, for each creator-selected popup sub-question, the distribution of
  answers in that cell with buckets under K masked (choices) or hidden (a mean of fewer than K
  numbers). Exact geometries stay in Responses and the export.
- `PublicResultsService` masks through `data.aggregate.mask`; `public_results_grid.spray_grid`
  becomes a thin wrapper over `data.aggregate.grid`.
- The snapshot format version goes from 2 to 3: a page frozen with point features asks its creator
  to refresh instead of showing points (no frozen page exists in production on 2026-11-14).
- The public renderer draws the grid for every map block (one renderer, the spray one) and shows
  the per-cell popup.
- API and MCP numbers do not change.

## Capabilities

### New Capabilities
- `public-aggregates`: the one path for anything a public surface shows of answers — masking,
  grids, and the rule that a public map never carries an individual geometry.

### Modified Capabilities
- `public-results-page`: "Anonymous geo display" becomes a grid of cells with per-cell, masked
  popup distributions.

## Impact

- Code: new `data/aggregate.py`; `survey/public_results.py` (`_map_payload`, `_mask`),
  `survey/public_results_grid.py` (wrapper), `survey/models.py` (`PUBLIC_RESULTS_SNAPSHOT_VERSION`),
  `survey/assets/js/public_results_render.js` (grid popups for every map block). No migration.
- Users: the 22 published results pages with a geo map block show cells after the epic ships;
  creators keep exact points in Responses and the export. Help page for public results updated.
- Tests: new `survey/tests/test_public_aggregates.py`; public-results tests that asserted point
  features updated.
