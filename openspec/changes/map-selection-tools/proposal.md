## Why

The analytics map currently supports only single-click selection. Users need QGIS-style tools to select multiple features by area (rectangle, polygon) and inspect individual session details. This is essential for geographic analysis workflows.

## What Changes

- **Map toolbar** with 4 tools: Pointer, Rectangle Select, Polygon Select, Details
- **Rectangle select**: draw rectangle → select all features within → cross-filter
- **Polygon select**: click points to draw polygon → select features within → cross-filter
- **Ctrl+click multi-select** in Pointer mode
- **Session details modal**: click feature in Details mode → modal with all answers + mini-map

## Capabilities

### New Capabilities

- `map-selection-tools`: QGIS-style toolbar on analytics map with pointer, rectangle, polygon select, and session details tools.
- `session-detail-modal`: HTMX endpoint + Bootstrap modal showing all answers for a session with mini-map.

### Modified Capabilities

- `geo-click-select`: Extended with Ctrl+click multi-select via `toggleGeoSid()`.
- `cross-filtering`: FilterManager extended with `toggleGeoSid()` method.

## Impact

- **New files**:
  - `survey/templates/editor/partials/analytics_session_detail.html`
- **Modified files**:
  - `survey/analytics_views.py` — new `analytics_session_detail` view
  - `survey/urls.py` — new URL pattern
  - `survey/templates/editor/analytics_dashboard.html` — Leaflet.draw CDN, toolbar CSS, `toggleGeoSid()`
  - `survey/templates/editor/partials/analytics_geo_map.html` — toolbar control, draw handlers, mode-aware click handlers, modal shell

## Out of Scope

- Freehand drawing (true mouse-drag lasso)
- Image answer display in details modal
- Export selected features
