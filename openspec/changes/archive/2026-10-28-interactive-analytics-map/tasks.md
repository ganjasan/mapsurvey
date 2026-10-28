## 1. Focus Mode

- [x] 1.1 Add focus mode CSS to `analytics_dashboard.html`: `.focus-mode` grid, `.is-focused`, `#analytics-sidebar-wrapper`, `.expand-btn`
- [x] 1.2 Add `enterFocusMode(sectionEl)` and `exitFocusMode()` JS functions
- [x] 1.3 Add expand button to each question section in `analytics_question_stats.html`
- [x] 1.4 Add expand button to geo map section in `analytics_geo_map.html`
- [x] 1.5 Handle Chart.js resize and Leaflet `invalidateSize()` after layout change

## 2. Geo Layer Toggles

- [x] 2.1 Rewrite geo map script: build `window.geoFeatureLayers` flat array with `{layer, sid, question}` metadata
- [x] 2.2 Build `window.geoQuestionVisible` Map (all true initially)
- [x] 2.3 Expose `window.analyticsMap` for external `invalidateSize()` calls
- [x] 2.4 Build collapsible legend as `L.Control` with checkboxes per question
- [x] 2.5 Add legend CSS to `analytics_dashboard.html`
- [x] 2.6 Rewrite `FilterManager._updateGeoMap()` to use flat array + dual visibility check (filteredSids AND geoQuestionVisible)

## 3. Click-to-Select

- [x] 3.1 Add `this.geoSelection = null` to FilterManager constructor
- [x] 3.2 Add `FilterManager.prototype.setGeoSelection(sids)` method
- [x] 3.3 Update `FilterManager.prototype._recompute()` to intersect geoSelection
- [x] 3.4 Add `FilterManager.prototype._updateGeoMapSelection()` for highlight styles
- [x] 3.5 Update `FilterManager.prototype._apply()` to call `_updateGeoMapSelection()`
- [x] 3.6 Update `FilterManager.prototype._updatePills()` to render geo-selection pill
- [x] 3.7 Add per-feature click handler in geo map calling `setGeoSelection`
- [x] 3.8 Add map background click handler for deselect (with `L.DomEvent.stopPropagation` on feature clicks)
