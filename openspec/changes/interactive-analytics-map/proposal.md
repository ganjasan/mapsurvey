## Why

The analytics map currently shows all geo features as static colored dots — no interactivity beyond zoom/pan. Users cannot toggle individual geo layers, select features to cross-filter other charts, or expand the map for detailed exploration. This limits the analytical value of geographic data.

## What Changes

- **Focus mode** for any analytics section: expand to 2/3 screen with sidebar showing other questions (1/3). Works for map, charts, text — any question.
- **Geo layer toggles**: collapsible legend with checkboxes per geo-question to show/hide layers.
- **Click-to-select on map**: click a geo feature to select its session, cross-filtering all other charts. Click empty area to deselect.

## Capabilities

### New Capabilities

- `focus-mode`: Expand any analytics question to 2/3 of the screen with a scrollable sidebar showing all other questions. Pure CSS/JS layout toggle.
- `geo-layer-toggles`: Collapsible legend overlay on the analytics map with per-question checkboxes to show/hide geo layers.
- `geo-click-select`: Click a geo feature to select its session and cross-filter all charts, map, and text answers.

### Modified Capabilities

- `cross-filtering`: FilterManager extended with `geoSelection` field for session-based filtering from map clicks. `_recompute()` intersects choice filters with geo selection.

## Impact

- **Modified files** (all client-side, no server changes):
  - `survey/templates/editor/analytics_dashboard.html` — focus mode CSS/JS, FilterManager extensions
  - `survey/templates/editor/partials/analytics_geo_map.html` — flat feature array, layer toggles, click handlers
  - `survey/templates/editor/partials/analytics_question_stats.html` — expand button per question

## Out of Scope

- Rectangle select / lasso select (iteration 2)
- Session details modal (iteration 2)
- Server-side changes
