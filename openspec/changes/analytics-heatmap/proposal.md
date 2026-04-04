# Heatmap Sub-Layers for Analytics Geo Map

## Problem
The analytics dashboard shows individual geo-answer markers on the map, but there's no way to visualize spatial density patterns. Users must mentally aggregate hundreds of points to understand hotspots — the core value proposition of a map-based survey tool.

## Solution
Add heatmap sub-layers to the analytics Response Map. Each Point-type question layer gets an optional heatmap sub-layer that visualizes answer density using a standard gradient. Introduce a `LayerManager` abstraction to manage layer visibility, z-order, and heatmap lifecycle — providing a clean extension point for future geo-analytics features.

## Key Decisions
- **LayerManager replaces flat globals** — `window.geoFeatureLayers`, `geoQuestionVisible`, `geoGroup` are replaced by a single `LayerManager` with slots per question. `getFeatureLayers()` provides backward-compatible flat array for existing draw-select and FilterManager code.
- **Leaflet map panes for z-order** — each question gets a dedicated pane pair (points + heat). Reorder = reassign `zIndex`, no layer remove/re-add flicker.
- **Heatmap reacts to cross-filtering** — uses `_mapSids` (choice + numeric + time filters). Heatmap is NOT clickable/filterable itself.
- **Points and heatmap are independently toggleable** — legend shows heatmap as indented sub-item under parent layer.
- **Drag-and-drop layer reorder** in legend via SortableJS (already loaded). z-order on map matches legend order.
- **Only Point questions** get heatmap sub-layers. Line/polygon questions have no heatmap option.
- **Standard gradient, fixed settings for v1** — radius 20, blur 25, default red-yellow-green.

## Non-Goals
- Heatmap settings UI (radius/blur sliders) — future enhancement
- Per-question heatmap color customization — future
- Heatmap for line/polygon centroids — future
- Heatmap export as image — future

## Files Affected
- `survey/templates/editor/analytics_dashboard.html` — CDN script, CSS, FilterManager method updates
- `survey/templates/editor/partials/analytics_geo_map.html` — LayerManager, legend rewrite, heatmap init
- No backend changes
