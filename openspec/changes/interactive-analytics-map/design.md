## Context

The analytics dashboard is a single-column layout (max-width 1100px) with overview stats, daily chart, geo map, and per-question stats. Cross-filtering via FilterManager supports choice-code filters only. The geo map groups features by session_id for FilterManager integration. All JS is inline in Django templates.

## Goals / Non-Goals

**Goals:**
- Focus mode: expand any question to 2/3 screen, sidebar with others
- Geo layer toggles: collapsible legend with checkboxes per geo-question
- Click-to-select: click geo feature → cross-filter all charts by session
- All purely client-side, no server changes

**Non-Goals:**
- Rectangle/lasso select (iteration 2)
- Session details modal (iteration 2)
- New server endpoints

## Decisions

### 1. Focus mode via CSS grid + DOM restructuring
**Choice**: Toggle `.focus-mode` class on `.analytics-main`, JS moves non-focused sections into a sidebar wrapper div.
**Why**: CSS grid alone can't scroll a subset of siblings. Moving elements into a wrapper is simple, reversible, and works with existing Chart.js responsive mode.

### 2. Flat feature array for geo map
**Choice**: Replace session-only LayerGroup nesting with `window.geoFeatureLayers` flat array of `{layer, sid, question}`.
**Why**: Two visibility axes (session filter + question toggle) can't be cleanly expressed with nested LayerGroups. A flat array with dual predicate checking in `_updateGeoMap()` is simpler.

### 3. Geo selection as separate FilterManager field
**Choice**: `this.geoSelection: Set<sid> | null`, intersected with choice filters in `_recompute()`.
**Why**: Geo selection has no question ID or choice code — it's structurally different from choice filters. A separate field keeps the existing filters Map clean.

### 4. Legend as Leaflet L.Control
**Choice**: Build the legend using `L.Control.extend()` with `L.DomEvent.disableClickPropagation()`.
**Why**: Leaflet controls handle scroll/click isolation from the map. Prevents legend clicks from triggering map deselect.

### 5. Chart resize after layout change
**Choice**: `requestAnimationFrame` → `Chart.resize()` on all charts + `map.invalidateSize()`.
**Why**: Chart.js and Leaflet cache container dimensions. Must recalculate after CSS grid layout settles.

## Data Structures

### geoFeatureLayers (flat array, replaces nested LayerGroups)
```js
window.geoFeatureLayers = [
  { layer: L.circleMarker, sid: 42, question: "Location" },
  { layer: L.geoJSON, sid: 43, question: "Route" },
  ...
]
```

### geoQuestionVisible (display preference, not a filter)
```js
window.geoQuestionVisible = new Map([["Location", true], ["Route", true]])
```

### FilterManager.geoSelection (new field)
```js
this.geoSelection = null;  // null = no selection, Set<sid> = selected sessions
```

## Component Design

### FilterManager extensions
- `setGeoSelection(sids)` — replace geoSelection, call `_apply()`
- `_recompute()` — after choice-filter loop, intersect with geoSelection if non-null
- `_updateGeoMap()` — rewritten: iterate geoFeatureLayers, check both filteredSids AND geoQuestionVisible
- `_updateGeoMapSelection()` — new: highlight/unhighlight features based on geoSelection
- `_updatePills()` — add geo-selection pill

### Focus mode functions
- `enterFocusMode(sectionEl)` — create sidebar wrapper, move sections, add classes, resize charts/map
- `exitFocusMode()` — restore DOM order, remove classes, resize
- `window.focusedSection` — ref to currently focused element

### Geo map changes
- Flat feature array instead of nested session groups
- Per-feature click handler → `filterManager.setGeoSelection(new Set([sid]))`
- Map click → `filterManager.setGeoSelection(null)` (deselect)
- L.Control legend with checkboxes
- `window.analyticsMap` exposed for `invalidateSize()` calls
