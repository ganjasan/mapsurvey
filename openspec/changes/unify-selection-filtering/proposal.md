## Why

The analytics dashboard has two independent state managers (SelectionManager and FilterManager) that don't compose properly. Selection (highlight) only partially syncs across components. Hiding/keeping sessions is client-side CSS only — charts, timeline, and numeric stats ignore hidden sessions entirely. The timeline range slider is broken (`filterManager.setTimeSelection` doesn't exist). Chart bar clicks go through FilterManager (data filtering) instead of SelectionManager (highlight), creating a conceptual mismatch.

## What Changes

- **Clean separation**: SelectionManager = pure highlight overlay (`_selected` only). FilterManager = all visibility state (choice + numeric + time range + hidden sessions).
- **`visibleSids`**: single computed set that ALL components (charts, map, timeline, stats, table) use as their data universe.
- **Hide/Keep/Show on FilterManager**: `hideSelected()`, `keepOnlySelected()`, `showAll()` move from SelectionManager to FilterManager, triggering full `_apply()` recompute.
- **Fix timeline slider**: add `setTimeRange(from, to)` to FilterManager, integrate into `_recompute()`.
- **Chart bar click = selection**: clicking a choice bar selects matching sessions via SelectionManager instead of filtering.
- **`_renderSelection()`**: single consolidated method for all selection visual updates (map opacity, chart colors, table checkboxes, panel bars).

## Capabilities

### New Capabilities

- `time-range-filter`: Timeline range slider filters all components (charts, map, stats, table) — currently broken.
- `hidden-as-filter`: Hidden sessions excluded from all computations (chart counts, timeline buckets, numeric stats, map features).

### Modified Capabilities

- `cross-filtering`: FilterManager._recompute() now intersects choice + numeric + time range + hidden exclusion into `visibleSids`.
- `chart-interaction`: Choice chart bar click selects sessions (SelectionManager) instead of filtering (FilterManager). Histogram slider stays as filter.
- `selection-rendering`: All selection visual feedback (map, charts, table, pills) consolidated into FilterManager._renderSelection().

## Impact

- **Modified files** (all client-side, no server changes):
  - `survey/templates/editor/analytics_dashboard.html` — SelectionManager trimmed, FilterManager extended, onChange consolidated
  - `survey/templates/editor/partials/analytics_question_stats.html` — chart onClick → selectionManager
  - `survey/templates/editor/partials/analytics_daily_chart.html` — setTimeSelection → setTimeRange
  - `survey/templates/editor/partials/analytics_geo_map.html` — minor: remove dead _updateGeoMapSelection call

## Out of Scope

- Server-side hidden session filtering (table still uses client-side CSS hiding for hidden rows)
- Histogram bar click → selection (histogram slider stays as numeric range filter)
- Persisting hidden/selection state across page navigations
