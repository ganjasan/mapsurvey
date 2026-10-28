## Why

A creator who uploads reference layers (zones, boundaries, a plan) in Survey settings sees them
on the respondent map and in the editor preview — and then opens the Responses tab to read the
collected geometry against exactly those zones, and the zones are gone. The Responses map, the
per-response map modal and the session mini-map all render bare basemaps. The
`reference-overlay-layers` spec never listed Responses in scope, so this is a gap in the
requirements, not a regression.

There is also a hard blocker underneath the UI gap: the layer endpoint
(`survey_layer_geojson`) reuses `check_survey_access`, which bypasses status checks only for the
`editor`+ roles. A `viewer` (who is allowed into Responses) gets 404 on a draft/testing survey's
layers, and **everyone, the owner included, gets 404 on a closed survey** — the survey state where
Responses matters most.

## What Changes

- The Responses **Map pane** renders the survey's reference layers beneath answer geometry,
  with the same styling and labels respondents see, toggleable through the existing layers
  control. All layers are shown regardless of per-section `hidden_layers` (the pane aggregates
  every section). Layer features are non-interactive there, so they never steal a click from
  selection tools or answer popups.
- Reference layers are managed from the Map pane's own **Layers panel** (top-left), not from a
  second Leaflet layers control: each layer is a row with a checkbox, a colour swatch, zoom-to,
  drag-reorder and an opacity slider. Stacking order follows the panel, top row on top. Order,
  visibility and opacity are remembered per survey in the creator's browser (localStorage) and
  affect nothing outside the Responses tab.
- The Map pane renders its map when the survey has reference layers even before any geo
  answer exists, so a creator can verify zones against an empty survey.
- The **full-size response map modal** (`session-geo-map-modal`) renders the same layers, so a
  single response can be read against the plan. The 200-px session mini-map stays bare — it is a
  thumbnail.
- `survey_layer_geojson` serves a layer to any authenticated user holding at least the `viewer`
  role on the survey, regardless of survey status. Anonymous/respondent access is unchanged.
- Layer-building JS (style resolution, circle markers, escaped labels) is extracted from
  `partials/reference_layers.html` into a shared factory so the respondent page and the
  Responses surfaces cannot drift apart in styling.
- The per-survey cap rises from 5 to 10 layers (`MAX_LAYERS_PER_SURVEY`). Reading answers against
  several overlays — boundary, zones, a route, stops — is exactly what Responses is for, and five
  was an MVP storage guess, not a product limit (owner decision 2026-09-01).
- Everything stays behind the existing `MAP_REFERENCE_LAYERS` kill switch.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `reference-overlay-layers`:
  - ADDED — the Responses Map pane and the per-response map modal render reference layers.
  - MODIFIED — "Layer geometry is served by a gated cacheable endpoint": a survey collaborator
    with the `viewer` role or above is served the layer in every survey status.
  - MODIFIED — "Creator uploads and configures a reference layer": ≤10 layers per survey.
  - MODIFIED — "Feature kill switch": the Responses surfaces are listed among what the flag
    hides.

## Impact

- `survey/views.py` — `survey_layer_geojson` gains the collaborator bypass; `_build_map_layers_metadata` is reused (moved next to the layers module or imported) by analytics.
- `survey/analytics_views.py` — `analytics_dashboard` passes `map_layers` into the context.
- `survey/templates/partials/reference_layers.html` — delegates layer construction to a new
  `partials/ref_layer_factory.html` (bare JS, `window.RefLayerFactory`), behaviour unchanged.
- `survey/templates/editor/partials/analytics_geo_map.html` — includes the factory, fetches
  layers, adds overlays to `window._layersControl`, relaxes the "no features → no map" early return.
- `survey/templates/editor/analytics_dashboard_v2.html` — the modal adds the cached layer
  geometry to its own map (no second fetch: geometry is cached per page by the Map pane's loader).
- `survey/tests.py` — new endpoint-access tests (viewer on draft, owner on closed, anonymous on
  closed still refused), context tests for `analytics_dashboard`, kill-switch tests.
- No migrations, no new dependencies, no change to the respondent page beyond the JS extraction.
- Public results page `/r/<slug>/` is deliberately out of scope (separate decision on what a
  public audience may see).
