## Context

The Responses Map pane (`editor/partials/analytics_geo_map.html`) is a `LayerManager` of slots:
`features` (one per geo question), `heat` (leaflet.heat over a Point source, created from the
layer menu), `reference` (creator overlays). The spray change added `L.SprayAgreementLayer`
(`survey/assets/js/spray_layer.js`): members are `{id, dots}` clouds, the layer bins every dot into
world-anchored metre cells (`style: 'grid'`, cell = extent/40, never < 20 m) or screen-pixel cells
(`style: 'heat'`), counts DISTINCT members per cell, and draws share-of-respondents. It is attached
to a spray `features` slot directly (`slot.sprayHeat`), not as a slot of its own.

Line and polygon answers are plain `L.geoJSON` with `fillOpacity: 0.2`; `createHeat` and the layer
menu are gated on `geomType === 'Point'`. Everything runs in the browser against the page's
`geoData` FeatureCollection; there is no server aggregate (#243 adds one).

Constraints: no model/query change (epic non-goal: coverage is derived at read time); keep the
spray rendering byte-for-byte; the Map pane starts hidden and 0×0 (every canvas draw must be
guarded, see `AnalyticsHeatLayerGuardTest`); prefs are browser-only; no kill switch (memory
`feedback_no_kill_switches`).

## Goals / Non-Goals

**Goals:**
- One layer class computes "share of respondents covering a cell" for clouds, polygons and lines.
- A `coverage` slot in the `LayerManager` with the full heat-slot lifecycle: create from the layer
  menu, filter with the session selection, show/hide, reorder, opacity, settings, remove.
- A reading that says "N of M respondents", never "hot".

**Non-Goals:**
- Exact counts for export / public results (#243), the agreement contour (#244).
- The Overview thumbnail and the per-response modal (stay as they are, like reference layers do).
- Weighting by a sub-question answer; per-feature popups on the surface.
- Changing how spray clouds are attached (they keep `slot.sprayHeat`; no migration of that path).

## Decisions

**D1 — Generalise `L.SprayAgreementLayer`, do not add a second canvas layer.**
Members become `{id, dots}` OR `{id, geometry}` (a GeoJSON geometry of type LineString,
Polygon, MultiLineString, MultiPolygon). The two code paths that bin a cloud
(`redraw` for `heat`, `_redrawGrid` for `grid`) are refactored around one `_cellsOf(member,
project, cellPx)` → iterable of cell keys; everything after the binning (share, blur, ramp, alpha,
fillRect) is untouched, so spray output does not change. Alternative rejected: a new
`L.CoverageLayer` copying 150 lines of rendering — two renderers for one statistic is exactly
the drift the epic exists to prevent. The class keeps its name for now (the spray change is still
open and names it in its spec); `L.CoverageLayer` can become an alias later.

**D2 — Rasterise shapes with an offscreen canvas at cell resolution.**
For a shape member: project its rings to world pixels at the current zoom, divide by `cellPx`,
draw onto an offscreen canvas whose pixel grid IS the cell grid (one pixel per cell), clipped to
the viewport cell range plus one cell of margin; polygons `fill('evenodd')` (holes are respected,
MultiPolygon parts one path), lines `stroke` with `lineWidth = max(1, corridorMeters / cellMeters)`
and round caps/joins. Read back the alpha channel: every non-zero pixel is a covered cell.
Alternatives: point-in-polygon per cell (O(cells × vertices), slow for a county-sized polygon at
40 cells across... fine, but a 5 000-vertex OSM-traced polygon times 1 600 cells per redraw is not);
Turf/martinez boolean overlay (an external dependency, combinatorial for 50 polygons). The
canvas rasteriser is what the browser does best, handles any ring count, and gives line
corridors for free. Precision is one cell, which is the resolution of the statistic anyway.

**D3 — Clip binning to the viewport.**
Only cells intersecting the visible map (plus margin) are counted and drawn, for shapes and for
dots alike (the `grid` style already skips off-screen cells at draw time; this moves the skip to
the binning so a city-wide polygon at zoom 18 does not allocate a 10⁶-cell canvas). Share is
unaffected: the denominator is members in scope, not cells.

**D4 — Coverage is a `coverage` slot, not a property of the source slot.**
Unlike spray (where the surface IS the question's rendering), a polygon layer keeps its shapes and
the coverage is an optional overlay the creator creates and removes — the heat-slot model. Slot
`coverage:<sourceId>`, own pane (panel order = stacking order, `_assignPaneZIndices` unchanged),
created by `createCoverage(sourceId)` from the layer menu, removed by `removeCoverage`, filtered in
`setFilter` via `surface.setFilter(sids)`, hidden/shown in `setLayerVisible` by add/remove from
the map (the spray pattern), opacity via the pane's CSS opacity (the reference-layer pattern),
options via `setCoverageOptions(id, {corridorMeters, cellMeters, style})`. The layer menu renders
for `LineString`/`Polygon`/`Multi*` sources with a *Create Coverage* entry; Point sources keep
*Create Heatmap* only (a Point coverage is a heatmap with a worse ramp).

**D5 — Corridor in metres, cell size from extent, both editable.**
Lines are buffered by `corridorMeters` (default 20 m, one urban street) at bin time; a corridor
thinner than a cell still covers one cell. Cell size follows the spray rule (longer side / 40,
≥ 20 m) and is overridable in the settings popover (`cellMeters`, 10 m … 1 000 m). Both are
layer options, so a redraw at a new zoom keeps their meaning; a pixel corridor would change
meaning with every zoom.

**D6 — Legend states the count.**
The panel row shows "≤ N of M respondents" (max covering count / members in scope) computed by the
layer after each redraw (`getStats()`), and the settings popover repeats it. The ramp or colour
alone would read as "hot"; the number is the point of the feature.

**D7 — Prefs: same keys as other slots, not recreated on load.**
Order/visibility/opacity of a `coverage` slot persist through `_saveRefPrefs` like every slot id in
`getSlotIds()`; the slot itself is NOT recreated on page load (heat slots are not either). Options
(`corridorMeters`, `cellMeters`) are therefore per page-view. Recreating coverage on load is a
separate, small follow-up if creators ask.

**D8 — Tests at the template contract + one pure JS seam.**
Django tests (`CoverageSurfaceTest`) render the v2 Responses page with line/polygon answers and
assert the hooks the page must carry (`createCoverage`, the menu gating on non-point geometry,
the guard around canvas draws, the stats line). `L.SprayAgreementLayer._cellsOf` is written so a
Node-free check is possible: a Django test ships the JS through the existing pattern of asserting
function presence and signature, as `AnalyticsHeatLayerGuardTest` does — no JS runner exists in
this repo and this change does not add one. Manual verification on the dev server with a seeded
survey (the Copenhagen demo has polygon and line questions).

## Risks / Trade-offs

- [`getImageData` on a canvas the Map pane sized at 0×0 throws] → every draw goes through the
  existing `redraw` guard (`!this._map || !this._canvas`) plus a size check before allocating the
  offscreen canvas; `whenMapSized` gates slot creation like heat.
- [A huge polygon count × high zoom makes rasterisation slow] → viewport clipping (D3), one
  offscreen canvas reused across members, redraw only on `moveend`/`zoomend` (already the
  layer's behaviour). 50 polygons × 1 600 cells is trivially fast; the risk is a 10 000-vertex
  polygon, which the canvas handles natively.
- [Alpha read-back counts anti-aliased edge pixels as covered] → draw with
  `imageSmoothingEnabled = false` and treat alpha ≥ 128 as covered; edge error ≤ half a cell.
- [Creators read a lone respondent's polygon as "agreement"] → the row and popover say "1 of M
  respondents"; opacity floor stays at `minAlpha`, as for spray.
- [Spray output drifts during the refactor] → the spray read-surface tests stay green and a
  before/after screenshot of the Copenhagen spray question is attached to the PR.
- [Rollback] → revert the PR; no data, no migration, no settings.

## Open Questions

- Should the Overview thumbnail show coverage when a coverage slot exists? Deferred: thumbnail
  stays bare (as for reference layers) until asked.
- Default corridor 20 m: confirm with the first route-survey creator who uses it.
