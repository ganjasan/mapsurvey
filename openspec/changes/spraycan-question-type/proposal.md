## Why

Our three geo question types all ask the respondent for a boundary: a point, a line or a polygon
with a hard edge. Many participatory questions have no boundary — "where does the city centre
end?", "where do you feel unsafe?", "where is it unbearably hot in summer?" — and a polygon forces
a precision the respondent does not have, so they either skip the question or draw a shape that
says more than they know. Map-Me (Huck, Whyatt & Coulton, *Spraycan: A PPGIS for capturing
imprecise notions of place*, Applied Geography 2014) solved this with an airbrush: the respondent
sprays dots, the density of paint carries confidence, and the result is a cloud rather than a
shape. Gemini named Map-Me in the AI search panel (2026-09-05) as a question type we lack; the
PPGIS research community, where our best-converting segments (student cohorts, universities) live,
knows the method by name. Two surveys already in view need it: the Reddit showcase survey "where
does the centre end" and the Bishkek heat map, where felt heat is exactly a fuzzy area.

## What Changes

- A new geo question type `spraycan`: the respondent paints an area on the map with an airbrush
  brush (mouse or finger), in an explicit paint mode with Spray / Erase / Move map tools and the
  existing bottom action bar (Cancel / Finish). The answer is ONE feature per respondent per
  question, stored as a `MultiPoint` of spray dots (Map-Me's model); creators set the brush
  colour and brush size, and whether the question is required (at least one dot).
- `Answer` gets a `multipoint` geometry column and a migration; no dot cap by default, the
  creator may set one per question.
- Every consumer of geo answers learns the type: section POST parsing and validation, session
  restore, the Responses Map pane (density surface through `leaflet.heat`, per-question layer),
  the Overview thumbnail, the per-response map modal and drawer, sub-question popups
  (`spraycan` joins `PARENT_TYPES`), data export in every format (GeoJSON `MultiPoint`, the
  observations table with centroid `lat`/`lon` + `wkt` + `dot_count`, GPKG/SHP/KML as MultiPoint
  layers), survey ZIP export/import of the new question settings, AI draft generation (the type
  is offered to the model with guidance on when to use it), the editor type picker and question
  modal (brush settings, live preview), conditional-visibility checks (a spraycan question is
  never a controller), duplication and cross-survey paste.
- Public results: a map block over a spraycan question publishes a density grid aggregated
  server-side (cells of distinct-respondent counts, cells below the page's k-anonymity threshold
  masked), never the raw dots of any respondent.
- Explicit non-goals for this change: a spraycan question cannot be the source of a shared-map
  (`question`-sourced) reference layer; Map-Me's stroke metadata (order, timing, brush size per
  stroke) is not stored; no "multiple sprays per question" — one cloud per respondent.
- An in-app changelog entry ships with the change.

## Capabilities

### New Capabilities
- `spraycan-question`: the `spraycan` input type end to end — data model and limits, the
  respondent paint mode (tools, touch handling, Cancel/Finish, sub-question popup), editor
  settings and preview, how the type behaves in features that enumerate geo types (visibility,
  form layout, shared map, duplication).
- `spraycan-density-views`: how spray clouds are read back — the Responses Map pane / Overview
  thumbnail / response modal, and the public results density grid with k-anonymity.

### Modified Capabilities
- `responses-export-formats`: the observations table and the GIS writers gain the `MultiPoint`
  geometry type (centroid `lat`/`lon`, `wkt`, a `dot_count` column) — "one row per placed
  feature" now includes a spray cloud as one feature.
- `survey-serialization`: the geo-field handling on import/export covers `spraycan` and its
  brush settings round-trip verbatim.
- `question-type-picker`: `spraycan` appears in the map-questions group with icon, hint and
  example, and the question modal shows brush settings for it.
- `section-form-layout`: the geo exclusion for `form` sections names `spraycan` with the other
  geo types.
- `ai-survey-generation`: the allowed-type list given to the model includes `spraycan` with
  guidance; the validation gate accepts it.

## Impact

- **Models / migrations**: `survey/models.py` — `INPUT_TYPE_CHOICES`, geo-type sets
  (`GEO_INPUT_TYPES`, `PARENT_TYPES`, …), new `Question` brush fields, new
  `Answer.multipoint` (`MultiPointField`, srid 4326); one migration.
- **Respondent**: `survey/forms.py` (new field + widget), `base_survey_template.html` and the
  draw JS (new paint mode with its own canvas layer, `#drawbar` reuse), `main.css`,
  `i18n_extras.py` tool labels, the section POST view (parse/validate/save MultiPoint, cap dots),
  restore-on-return.
- **Responses**: `survey/analytics*.py`, `analytics_geo_map.html`, Overview thumbnail, session
  modal/drawer — a density layer per spraycan question through the existing `leaflet.heat`.
- **Export**: `survey/export.py` collector and every writer; OGR VRT layer geometry type.
- **Public results**: `survey/public_results.py` (`_map_payload` branch, grid aggregation,
  snapshot version bump), `public_results.html` renderer.
- **Editor**: type picker metadata + parity test, question modal fields, live preview,
  `cloning.py`, `visibility.py` lint, `serialization.py`, AI prompt and validator.
- **Tests**: `survey/tests.py` — model/POST/export/public-results/picker-parity coverage.
- **Dependencies**: none new; Leaflet 1.4.0 canvas API and `leaflet.heat` already in use.
- **Changelog**: `survey/changelog/<date>-spraycan-question.html`.
