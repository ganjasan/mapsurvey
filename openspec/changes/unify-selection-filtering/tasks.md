## 1. Fix Timeline Range Filter

- [ ] 1.1 Add `this.timeRange = null` and `this._hiddenSids = new Set()` and `this.visibleSids = null` and `this._choiceNumericSids = null` to FilterManager constructor
- [ ] 1.2 Add `FilterManager.prototype.setTimeRange(from, to)` — stores `{from, to}` or null, calls `_apply()`
- [ ] 1.3 Update `_recompute()`: add time range intersection step (scan `_sessionHours` for matching SIDs), produce `visibleSids` and `_choiceNumericSids`
- [ ] 1.4 Update `clearAll()`: add `this.timeRange = null; if (window._resetTimelineHandles) window._resetTimelineHandles();`
- [ ] 1.5 Add time range pill in `_updatePills()`
- [ ] 1.6 Update `analytics_daily_chart.html`: replace `filterManager.setTimeSelection(matchingSids)` with `filterManager.setTimeRange(fromTs, toTs)`, fix `onReset`, remove local SID computation from `onFilter`
- [ ] 1.7 Update `_updateTimeline()` to use `_choiceNumericSids` (timeline cross-filters by choice/numeric only, not by own time range)

## 2. Move Hidden to FilterManager

- [ ] 2.1 Add `FilterManager.prototype._visibleMatrix()` — returns `_matrix.filter(s => !_hiddenSids.has(s.sid))`
- [ ] 2.2 Add `FilterManager.prototype.hideSelected()` — reads `selectionManager.getSelected()`, adds to `_hiddenSids`, calls `selectionManager.clear()`, calls `_apply()`
- [ ] 2.3 Add `FilterManager.prototype.keepOnlySelected()` — adds all non-selected visible IDs to `_hiddenSids`, clears selection, calls `_apply()`
- [ ] 2.4 Add `FilterManager.prototype.showAll()` — clears `_hiddenSids`, calls `_apply()`
- [ ] 2.5 Add `FilterManager.prototype.getVisibleSids()` — returns `this.visibleSids`
- [ ] 2.6 Update `_recompute()` to subtract `_hiddenSids` from result → `visibleSids`
- [ ] 2.7 Swap `this._matrix` to `this._visibleMatrix()` in: `_recompute`, `_crossFilterSids`, `_computeCountsFrom`, `_updateNumericStats`
- [ ] 2.8 Update `_updateTimeline()` to skip hidden sessions from `_sessionHours`
- [ ] 2.9 Update `_updateGeoMap()` to use `this.visibleSids`
- [ ] 2.10 Update `_updateCharts()` to use `this.visibleSids` for non-source chart counts
- [ ] 2.11 Update `clearAll()` to also clear `_hiddenSids`
- [ ] 2.12 Update button onclick attrs: `selectionManager.hideSelected()` → `filterManager.hideSelected()` (in panel-selection-bar for map and charts panels, and table bulk toolbar)
- [ ] 2.13 Update "Show all" button: `selectionManager.showAll()` → `filterManager.showAll()`

## 3. Consolidate Rendering into _renderSelection()

- [ ] 3.1 Create `FilterManager.prototype._renderSelection()` with logic from current onChange handler: panel selection bars, hidden indicator, table checkbox sync, map feature styling, chart color highlighting, pills update
- [ ] 3.2 Register `_renderSelection` as last component in `_apply()` pipeline
- [ ] 3.3 Replace SelectionManager.onChange listener body with single call to `filterManager._renderSelection()`

## 4. Chart Bar Click = Selection

- [ ] 4.1 Update choice chart `onClick` in `analytics_question_stats.html`: compute matching SIDs from matrix (filtered by `visibleSids`), call `selectionManager.setSelection(ids)` with toggle (if same set already selected, clear)

## 5. Strip SelectionManager

- [ ] 5.1 Remove from SelectionManager: `_hidden`, `hideSelected`, `keepOnlySelected`, `showAll`, `isHidden`, `getHidden`, `hiddenCount`, `hasHidden`
- [ ] 5.2 Update `invert()` to use `filterManager.getVisibleSids()` as universe instead of `_allSessionIds`

## 6. Cleanup

- [ ] 6.1 Remove `FilterManager.prototype._updateGeoMapSelection` (empty stub)
- [ ] 6.2 Remove its registration in component pipeline
- [ ] 6.3 Remove dead code `if (false)` timeline pills guard in `_updatePills`
- [ ] 6.4 Remove old bulk toolbar visibility logic from onChange (now in `_renderSelection`)
