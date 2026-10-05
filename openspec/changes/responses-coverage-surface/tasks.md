## 1. Generalise the agreement layer (`survey/assets/js/spray_layer.js`)

- [x] 1.1 Accept members `{id, dots}` or `{id, geometry}` in `L.SprayAgreementLayer`; `getBounds()` covers both kinds
- [x] 1.2 Extract one binning seam `_cellsOf(member, project, cellPx, range)` used by both `redraw` (heat style) and `_redrawGrid`; dots path unchanged
- [x] 1.3 Shape rasteriser: offscreen canvas at cell resolution clipped to the viewport range, `fill('evenodd')` for polygons/multipolygons, `stroke` with corridor-in-cells for lines, alpha ≥ 128 read-back, `imageSmoothingEnabled = false`
- [x] 1.4 Options `corridorMeters` (default 20) and user-set `cellMeters`; `setStyle` redraws with them
- [x] 1.5 `getStats()` → `{max, respondents}` after each redraw, for the panel row and popover
- [x] 1.6 Static helper `L.SprayAgreementLayer.membersFromFeatures(features)` for line/polygon features (id = `session_id`), beside `cloudsFromFeatures`

## 2. `LayerManager` coverage slot (`editor/partials/analytics_geo_map.html`)

- [x] 2.1 `createCoverage(sourceId)` / `removeCoverage(id)` / `hasCoverageFor(sourceId)` / `setCoverageOptions(id, opts)`; slot `{id: 'coverage:<src>', type: 'coverage', sourceId, surface, pane, visible, opacity}`; creation gated by `whenMapSized`
- [x] 2.2 `setFilter` calls `surface.setFilter(sids)` for coverage slots; `setLayerVisible` adds/removes the surface; opacity through the pane's CSS opacity
- [x] 2.3 Layer menu: *Create Coverage* / *Coverage exists* for LineString/Polygon/Multi* sources; menu button rendered for those geometries (today Point only); Point sources unchanged
- [x] 2.4 Panel row for `coverage`: swatch in layer colour, rename, opacity, settings, remove, count line "≤ N of M respondents" refreshed on the surface's redraw
- [x] 2.5 Settings popover: cell size (10–1000 m) and, for line sources, corridor (5–500 m); live redraw; shows the count line
- [x] 2.6 Prefs: coverage slot ids flow through `_saveRefPrefs`/`_syncOrderFromPanel` like heat slots (no recreation on load)
- [x] 2.7 CSS for the coverage row/swatch in the analytics stylesheet, reusing the heat row classes where they fit

## 3. Tests and verification

- [x] 3.1 `CoverageSurfaceTest` (Django): the v2 Responses page with a polygon and a line question carries `createCoverage`, the menu gating on non-point geometry, `getStats`, and the sized-map guard; a Point-only survey offers no coverage entry
- [x] 3.2 Spray tests (`SpraycanReadSurfacesTest`, `SpraycanPublicGridTest`) stay green after the refactor
- [x] 3.3 Manual check on the dev server (offset 460): polygon overlap darkens, line corridor slider redraws, table selection narrows the surface, remove restores the menu entry; before/after screenshot of a spray question for the PR
- [x] 3.4 `collectstatic`; `./run_tests.sh survey` baseline and after

## 4. Ship

- [x] 4.1 Changelog entry `survey/changelog/<release date>-coverage-surface.html` (kind `new`, link `editor`)
- [x] 4.2 CLAUDE.md: one paragraph on the coverage surface next to the shared-map/spray notes
- [ ] 4.3 PR "feat(responses): coverage surface for polygon and line answers (#242)" with `[render preview]`, closes #242, references #245
