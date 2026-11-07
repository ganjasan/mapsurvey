## Why

Step 3 of 4 of epic #348 (#578). "Transparency means showing your work": a landing that
stays live between rounds should show what residents said in the last one, next to the next
question. The public results page (`/r/<slug>/`) already aggregates a survey with privacy
protections; the landing should show the same charts and maps without a second aggregation.

## What Changes

- **Results block**: one question of a survey linked to the landing (choice, multichoice,
  rating, thumbs, number, range → chart; point, line, polygon, spray → map; objects on the map
  → table), with a visualisation (bar, pie, donut, table; markers, heatmap, clusters) and a
  base map for map questions.
- Payloads come from `PublicResultsService` — the same clean-session rule (canonical survey +
  versions, no deleted / not-approved / on-hold sessions), the same k-anonymity (the survey's
  results-page K when it has one, else 3), no free text, no map popups. Cached 60 s per block.
- The browser renderer of `/r/` moves from the template into `js/public_results_render.js`
  (`renderResultBlocks(blocks, basemaps)`), loaded by both pages: one renderer.
- Chart.js / Leaflet plugins load on a landing only when a results block needs them.

## Capabilities

### Modified Capabilities
- `survey-landings`: the closed block set grows by `results`; a requirement for results blocks.

## Impact

- `survey/landings.py` (`results` kind, cleaner, `results_payload`), `survey/public_results.py`
  (a constructor that takes a survey and K instead of a page — `PublicResultsService.for_survey`),
  `survey/landing_views.py` (question picker, survey link), templates
  `landings/blocks/results.html`, `public.html`, `public_results.html` (renderer include),
  new `survey/assets/js/public_results_render.js`, tests, help, translations.
- No model change (the block reuses `landing_survey` and stores the question CODE in `data`).
