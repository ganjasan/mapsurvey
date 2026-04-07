## Context

The analytics dashboard has two parallel state managers. SelectionManager (IIFE at analytics_dashboard.html:511-553) owns `_selected` and `_hidden` Sets with onChange pub/sub. FilterManager (constructor at analytics_dashboard.html:1545+) owns choice/numeric filters with a registered component pipeline (`_apply` → `_recompute` → components). They interact ad-hoc: SelectionManager.onChange overrides chart colors, FilterManager.clearAll calls selectionManager.clear(). Hidden sessions only affect map (opacity) and table (CSS display) — charts, timeline, and stats ignore them entirely.

## Goals / Non-Goals

**Goals:**
- Single `visibleSids` concept that all components consume
- Hidden sessions excluded from all computations (charts, timeline, stats, map)
- Working timeline range filter
- Chart bar click = session selection (not data filtering)
- One rendering path for selection highlights

**Non-Goals:**
- Server-side hidden session filtering for table pagination
- Merging the two managers into one class
- Changing histogram slider behavior (stays as numeric range filter)

## Decisions

### 1. Move `_hidden` to FilterManager as `_hiddenSids`
**Choice**: FilterManager owns all visibility state. SelectionManager becomes a pure highlight store.
**Why**: Hidden sessions must affect data computations (chart counts, stats, timeline). FilterManager already owns the computation pipeline (`_recompute` → component updates). Having FilterManager read `_hidden` from SelectionManager creates split ownership. Moving it makes the conceptual model clean: FilterManager = universe, SelectionManager = highlight overlay.

### 2. `visibleSids` as the unified output of `_recompute()`
**Choice**: `_recompute()` produces `this.visibleSids = intersect(choiceNumeric, timeRange) - hiddenSids`. All `_update*` components use `visibleSids` instead of the previous `filteredSids`/`_mapSids`/`_timelineSids` split.
**Why**: Currently there are 4 separate SID fields (`filteredSids`, `_choiceFilteredSids`, `_mapSids`, `_timelineSids`) that are all set to the same value. One field is simpler. The timeline cross-filter exception (timeline shouldn't filter itself) is handled by `_updateTimeline` reading `_choiceNumericSids` directly.

### 3. `_renderSelection()` as registered component
**Choice**: New `FilterManager.prototype._renderSelection` method registered last in the component pipeline. Also called directly from `selectionManager.onChange`. Contains all selection visual logic (map opacity, chart colors, table checkboxes, panel bars, hidden indicator).
**Why**: Currently the selection rendering is split: 80 lines in the SelectionManager.onChange listener + `_updateCharts` + `_updatePills`. These fight over chart colors. A single method called from both paths eliminates the conflict.

### 4. Timeline stores `timeRange` object, not pre-computed SIDs
**Choice**: `setTimeRange(from, to)` stores `{from, to}` strings. `_recompute()` scans `_sessionHours` to compute matching SIDs.
**Why**: The broken `setTimeSelection(sids)` approach required the slider to compute SIDs using its own `_sessionHours` scan, duplicating logic. Having FilterManager own the scan keeps the logic in one place and allows `_recompute()` to apply hidden exclusion consistently.

### 5. Chart bar click → selectionManager.setSelection with toggle
**Choice**: Clicking a choice chart bar computes matching session IDs from `_matrix` (filtered by `visibleSids`) and calls `selectionManager.setSelection(ids)`. Clicking the same bar again clears selection.
**Why**: User confirmed chart bars should SELECT (highlight across all components), not filter. Toggle behavior prevents "stuck" selection.

### 6. `clearAll()` does NOT clear selection
**Choice**: `clearAll()` clears filters + hidden + time range but leaves `_selected` untouched.
**Why**: Clearing filters and clearing selection are independent user intents. The user clears selection via the X button or "Selected (N) ×" pill.

## Architecture

```
SelectionManager (pure highlight)          FilterManager (data universe)
  _selected: Set<sid>                        filters: Map<qid, Set<code>>
  _allSessionIds: Set<sid>                   numericRanges: Map<qid, {min,max}>
  onChange → fm._renderSelection()           timeRange: {from,to} | null
                                             _hiddenSids: Set<sid>
                                             visibleSids: Set<sid> | null
                                             _choiceNumericSids: Set<sid> | null

                                             _recompute():
                                               choiceNumeric = intersect(choice, numeric)
                                               withTime = intersect(choiceNumeric, timeSids)
                                               visibleSids = withTime - _hiddenSids

                                             _apply() → components:
                                               _updateCharts (bar heights from visibleSids)
                                               _updateNumericStats
                                               _updateGeoMap (layerManager.setFilter)
                                               _updateTimeline (cross-filter: uses _choiceNumericSids)
                                               _updatePills
                                               _updateTextAnswers
                                               _updateTable
                                               _renderSelection (map opacity, chart colors, table checkboxes)
```

## Components

### FilterManager new methods
- `setTimeRange(from, to)` — stores time range, calls `_apply()`
- `hideSelected()` — reads `selectionManager.getSelected()`, adds to `_hiddenSids`, clears selection, calls `_apply()`
- `keepOnlySelected()` — adds all non-selected visible sessions to `_hiddenSids`, clears selection, calls `_apply()`
- `showAll()` — clears `_hiddenSids`, calls `_apply()`
- `getVisibleSids()` — returns `this.visibleSids`

### FilterManager modified methods
- `_recompute()` — adds time range intersection + hidden subtraction, produces `visibleSids` and `_choiceNumericSids`
- `clearAll()` — also clears `_hiddenSids`, `timeRange`, resets timeline handles
- `_updateCharts()` — uses `visibleSids` for non-source charts, `_crossFilterSids` still uses `_visibleMatrix()`
- `_updateTimeline()` — uses `_choiceNumericSids` (self-excluded from time), hidden excluded from `_sessionHours` scan
- `_updateNumericStats()` — uses `visibleSids`
- `_updateGeoMap()` — calls `layerManager.setFilter(visibleSids)`
- `_updatePills()` — adds time range pill, hidden count pill

### FilterManager helper
- `_visibleMatrix()` — returns `this._matrix.filter(s => !this._hiddenSids.has(s.sid))`. Used by `_recompute`, `_crossFilterSids`, `_computeCountsFrom`, `_updateNumericStats`.

### SelectionManager stripped down
- Remove: `_hidden`, `hideSelected`, `keepOnlySelected`, `showAll`, `isHidden`, `getHidden`, `hiddenCount`, `hasHidden`
- Modify `invert()`: uses `filterManager.getVisibleSids()` as universe
- Keep: `_selected`, `_allSessionIds`, select, deselect, toggle, clear, setSelection, isSelected, getSelected, count, hasSelection, onChange

### SelectionManager.onChange listener
- Replace 80-line body with: `if (window.filterManager) window.filterManager._renderSelection();`

### Template button changes
- Hide/Keep/Show buttons: `selectionManager.hideSelected()` → `filterManager.hideSelected()` etc.
- Timeline slider: `filterManager.setTimeSelection(sids)` → `filterManager.setTimeRange(from, to)`
- Choice chart onClick: `filterManager.toggleFilter(qid, code)` → `selectionManager.setSelection(matchIds)`
