## Context

`PublicResultsService._map_payload` emits each clean answer's GeoJSON geometry with the selected
sub-answers as popup properties; `_spray_grid_payload` already does the private thing for spray
clouds through `public_results_grid.spray_grid` (Web Mercator cells, distinct sessions per cell,
cells under K omitted). Site results blocks call `PublicResultsService.for_survey`, so they share
the payloads. Owner decision ADR-001 §6.3 (2026-11-14): public maps show cells, not points.

## Goals / Non-Goals

**Goals:** one grid for every geometry type; per-cell popups that keep the creator-selected
sub-question fields but only as masked distributions; masking in one module; frozen snapshots that
cannot keep serving points.

**Non-Goals:** consolidating feature converters, display values, lineage and choice counting
(`data.features`, the second change of #666); heat-surface styling options; API/MCP behaviour.

## Decisions

**D1 — `data.aggregate.grid(members, k, cells_across=40, min_cell_m=20.0)`.** `members` are
`(session_id, member_id, geometry)` in WGS 84. Geometries go to EPSG:3857; the cell size is the
spray rule (bbox longer side / `cells_across`, never under `min_cell_m`). Points and multipoints bin
by coordinate; lines and polygons bin into every cell their geometry intersects, tested with a
prepared geometry over the cells of its own bbox. A cell keeps the set of sessions and the set of
member ids; cells with fewer than K sessions are dropped before anything leaves the function.
Returns `{'cells': [{'bbox', 'respondents', 'members'}], 'max', 'respondents_total', 'cell_m'}`;
`members` are for the caller's per-cell summaries and are never serialised. `spray_grid` keeps its
signature and output by calling `grid` and stripping `members`.

**D2 — Per-cell popup.** For each selected popup sub-question code, the service reads the
sub-answers of the cell's member answers (clean sessions only): choice/multichoice/rating/thumbs →
`[{label, display}]` per option with `mask()` applied (zero counts left out); number/range → the
mean when at least K values exist in the cell, else nothing. Free text never (unchanged rule).
Properties: `{'respondents': n, 'fields': [{'name', 'values'|'mean'}]}` — no identifiers.

**D3 — Payload shape.** Every map block returns `data_type='grid'` with `cells`, `max`,
`respondents_total`, `cell_m`, `color` (question colour, else a neutral accent); the spray block is
the same code path with no popup fields. The renderer's `renderGrid` becomes the only map renderer
and binds a popup built with `textContent` when a cell has fields.

**D4 — Snapshot version 3.** `PUBLIC_RESULTS_SNAPSHOT_VERSION = 3`; `render_page_data` already
turns a version mismatch into the "ask the creator to refresh" state.

**D5 — Masking in one place.** `data.aggregate.mask(count, k)` returns the existing display dict;
`PublicResultsService._mask` delegates. Budget and object payloads keep their own modules' maskers
for now (they already mask; moving them is part of the `data.features` change).

## Risks / Trade-offs

- [Creators lose exact pins on the public page] → owner decision; Responses and export keep them;
  help page explains why.
- [Polygon binning cost] → bounded by cells_across² per geometry and prepared intersects; public
  payloads are cached 60 s.
- [A small survey shows an almost empty map] → expected with K; the caption states respondents and
  cell size, and K=1 shows every cell.

## Migration Plan

Code only; ships with the epic merge. Rollback = revert. No frozen page exists in production.
