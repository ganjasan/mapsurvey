## 1. data.aggregate

- [x] 1.1 `data/aggregate.py`: `mask(count, k)`; `grid(members, k, cells_across, min_cell_m)` for points, multipoints, lines and polygons (D1)
- [x] 1.2 `public_results_grid.spray_grid` → wrapper over `grid` (same output)
- [x] 1.3 `survey/tests/test_public_aggregates.py`: mask; grid for each geometry; distinct respondents; cells under K omitted; no geometry or ids in the output

## 2. Public results and Site blocks

- [x] 2.1 `PublicResultsService._map_payload` → grid payload for every geo type; per-cell popup fields (D2, D3); `_mask` delegates to `data.aggregate.mask`
- [x] 2.2 `PUBLIC_RESULTS_SNAPSHOT_VERSION = 3` (D4)
- [x] 2.3 `public_results_render.js`: every map block through `renderGrid`, popup built with `textContent`
- [x] 2.4 Update public-results tests that asserted point features; add spec scenarios (points become cells, polygon counted once per respondent per cell, popup distribution masked, frozen v2 snapshot is stale, Site results block same payload)

## 3. Docs

- [x] 3.1 Help page for public results: maps show cells, why, where the exact points are
- [x] 3.2 `CLAUDE.md`: public results paragraph names the grid and `data.aggregate`

## 4. Verify

- [x] 4.1 Touched modules + public results + sites tests green; full suite once
- [x] 4.2 `/verify`: a seeded survey's `/r/` map shows cells and a popup with masked counts
- [x] 4.3 `openspec validate data-aggregate --strict`
