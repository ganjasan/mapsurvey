## Why

A creator (survey 585, "Rower Miejski") opened Responses → Overview and got a Response Map tiled
entirely with OpenStreetMap's "Access blocked — 403 — App is not following the tile usage policy of
OpenStreetMap's volunteer-run servers" placeholder. We ship a paid Mapbox token to every browser
already, yet two surfaces still pull from volunteer-run servers: the Topo basemap
(`{s}.tile.opentopomap.org`, offered on every map) and the public results page, which loads
`{s}.tile.openstreetmap.org` directly. The second one is a standing violation of the OSM tile usage
policy on a page we ask creators to publish and promote, so it is a liability independent of the
report that surfaced it.

## What Changes

- Topo basemap moves from OpenTopoMap to **Mapbox Outdoors** (`mapbox/outdoors-v12`), served with
  the same public token as Streets. Max zoom rises 17 → 22 and tiles become retina (`@2x`).
- Public results page (`/r/<slug>/`) stops hard-coding tile URLs: `streets` and `topo` use the
  Mapbox URLs from settings, the same as every other map. `satellite` (Esri) is unchanged.
- The Outdoors URL becomes a setting (`MAPBOX_OUTDOORS_URL`) exposed through the existing `mapbox`
  context processor, so no template hard-codes a tile host — the same rule Streets already follows.
- After this change no Mapsurvey surface requests tiles from a volunteer-run server.
- Not a breaking change for creators: `basemaps` values (`streets`/`satellite`/`topo`) and
  `default_basemap` keep their meaning; only the Topo layer's provider and cartography change.

## Capabilities

### New Capabilities
- `basemap-providers`: which tile provider backs each basemap slug, on every surface that renders a
  map (respondent, editor, analytics, public results), and the rule that no surface may request
  tiles from a volunteer-run server.

### Modified Capabilities
<!-- No existing spec states tile-provider requirements; this is the first. -->

## Impact

- `mapsurvey/settings.py` — new `MAPBOX_OUTDOORS_URL` next to `MAPBOX_URL`.
- `survey/context_processors.py` — `mapbox()` also returns `MAPBOX_OUTDOORS_URL`.
- Templates: `partials/basemap_layers.html`, `base_survey_template.html`,
  `editor/survey_create.html`, `editor/partials/analytics_geo_map.html`,
  `editor/partials/analytics_session_detail.html`, `editor/partials/section_map_picker.html`,
  `public_results.html`.
- `survey/tests.py` — the basemap tile-URL assertions (one asserts `tile.opentopomap.org`).
- Cost: Topo and public-results traffic now counts against the Mapbox tile quota. Volume is small
  (Topo is rarely the default; public results pages are low-traffic), but it is no longer free.
- No migration, no model change, no env var required in production — the setting has a working
  default, exactly like `MAPBOX_URL`.
