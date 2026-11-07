## Context

`PublicResultsService(page, lang)` reads `page.survey` and `page.k_anonymity_threshold` and
builds a payload per `PublicResultsBlock` from `block.question`, `viz`, `custom_title`,
`geo_label_fields`, `basemap`. `/r/` renders the payloads with ~200 lines of inline JS
(Chart.js 4.4, Leaflet 1.4 + heat + markercluster).

## Decisions

### D1. Reference the question by code through the survey link
`data = {question_code, viz, basemap, caption}` and `landing_survey` → the canonical survey.
Codes survive `publish_draft()` (question rows are replaced, codes are not); the service's
lineage query is by code already. At render the question is the canonical survey's current
question with that code; a question deleted since → the block is not drawn (builder says why).
Unlinking the survey deletes the block (CASCADE, as for survey cards).

### D2. One aggregation: `PublicResultsService.for_survey(survey, k, lang)`
A classmethod that builds the service from a survey and K without a page. The landing passes a
duck-typed block (`SimpleNamespace` with the attributes `_build_block` reads; `id = "r<pk>"`,
`custom_title = {}`, `geo_label_fields = []` — no popups, `content = {}`, `image = None`) and
calls `_build_block`. K = the survey's results page's K when one exists, else the model default
(3). Text, datetime and other unpublishable types are refused at save.

### D3. One renderer
The inline script of `public_results.html` moves verbatim into
`js/public_results_render.js` as `window.renderResultBlocks(blocks, basemaps)`; the template
includes it and calls it with its blocks and basemap table. The landing calls it with the
results payloads and `basemaps.table_for(org)` (Mapbox token added by the caller as today).
Element ids are `chart-r<pk>`, `map-r<pk>`, `objects-r<pk>` — no clash with a landing map
block's `map-<pk>`.

### D4. Cache
Payload cached 60 s under `landing-results:<block pk>:<block updated_at>:<lang>`, matching the
live mode of `/r/`; a block edit changes the key. Member previews skip nothing — the same
payload.

## Risks / Trade-offs

- [Moving `/r/` JS breaks it] → verbatim move; the existing page tests now read the static
  file; dev check of `/r/` after the move.
- [Aggregation cost on a busy landing] → 60 s cache per block.
- [Publishing results the survey's own `/r/` does not show] → it is the creator's explicit act
  on a Pro feature, with the same masking; free text and popups are never offered.
