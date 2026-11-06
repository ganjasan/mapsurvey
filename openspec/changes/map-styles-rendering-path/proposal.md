## Why

A workspace-owned map style (epic #545, Vision and Scope in `openspec/docs/vision/map-styles.md`) needs a way to reach every map surface, and today all eight of them are Leaflet 1.4 over Mapbox **raster** tiles. Either the client renders a style JSON itself (vector tiles), or every custom style becomes a hosted style in the Mapsurvey Mapbox account and is served as raster, as Paper A / Paper B are now. The library (#542), the editor (#543) and import/export (#544) cannot be designed until this is decided (DE-1 / BR-1 of the vision), so the decision is its own change with a measured prototype behind it.

## What Changes

- A **prototype of both paths** on the respondent map with Paper A as the test style, reachable only on a dev stack (query parameter, never a setting), measured on the same survey and the same viewport.
- A **style publishing script** (`scripts/mapbox_style_publish.py`): takes a settings document (base preset + guided controls), produces a Mapbox GL style over `streets-v12`, creates or updates it in the Mapsurvey account through the Styles API and reports its id. This is the mechanism Paper A and B were built with by hand on 2026-11-06, written down as code; #542 reuses it whatever the decision.
- A **measurement record** for each path: billable requests and bytes per screen, first render on a mid-range phone, Leaflet code touched (draw, crosshair, layer switcher, heat, spray, reference layers), Mapbox limits (styles per account, Styles API rate limit, CDN propagation after an update, Static Images from a fresh style), and how each path produces the printed frame and the mark-recognition reference image (#534, #535).
- An **ADR** at `openspec/docs/adr/0001-map-style-rendering-path.md` naming the path, the measurements and the migration steps for #542–#544.
- Prototype code is **not merged**: only the script, the ADR and their tests reach `epic/map-styles`.

## Capabilities

### New Capabilities
- `map-style-rendering`: how a map style (system preset or workspace style) is rendered on a surface and published for print — the decision record, the publishing script and the measurement harness that produced it.

### Modified Capabilities
<!-- none: basemap-providers keeps its requirements; the resolved path will modify it in #542 -->

## Impact

- `scripts/mapbox_style_publish.py` (new), `survey/tests/test_map_style_rendering.py` (new), `openspec/docs/adr/` (new folder).
- Prototype-only, on the branch and not merged: `partials/basemap_layers.html`, `base_survey_template.html`, a MapLibre GL + `maplibre-gl-leaflet` include.
- Mapbox account: a handful of throw-away styles created and deleted during measurement; `MAPBOX_STYLES_TOKEN` gains `styles:write` for the script (never shipped to a browser).
- No model, migration or setting changes. No production surface changes.
- Depends on: `basemap-providers` spec (no volunteer tile hosts; one provider table), `printable-form` and `paper-photo-entry` specs (Static Images frame and reference image), issue #522 (512-px tiles — the raster baseline must be measured at 512 if #522 lands first).
