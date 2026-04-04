## 1. Infrastructure

- [ ] 1.1 Add `leaflet-heat.js` 0.2.0 CDN script tag to `analytics_dashboard.html` `{% block extra_head %}` after leaflet.draw
- [ ] 1.2 Add CSS rules to `analytics_dashboard.html`: `.geo-drag-handle`, `.geo-legend-row`, `.geo-legend-subitem`, `.geo-legend-heat-swatch`, `.sortable-ghost`, update `.geo-legend-item` to `display:block`

## 2. LayerManager Implementation

- [ ] 2.1 Write `LayerManager` constructor in `analytics_geo_map.html`: `_map`, `_slots` (Map), `_order` (array), `_sids` (null), `_BASE_Z=400`, `_STEP=10`
- [ ] 2.2 Write `LayerManager.prototype.init(map, geoData, colors)`: detect question names and geom types, create pane pairs (`geo-pane-N`, `geo-heat-N`), build `LayerSlot` per question with `features[]`, `allPoints[]`, `L.heatLayer`, assign initial z-indices
- [ ] 2.3 Write `_assignPaneZIndices()`: iterate `_order`, set `pane.style.zIndex = BASE + idx * STEP`, heat pane `+1`
- [ ] 2.4 Write `_rebuildHeat(slot)`: filter `slot.features` by `_sids`, extract `[lat, lng]`, call `slot.heatLayer.setLatLngs()`, add/remove from map
- [ ] 2.5 Write `setFilter(sids)`: store `_sids`, per slot: add/remove individual feature layers based on sid + visibility, call `_rebuildHeat` for visible heat layers
- [ ] 2.6 Write `setLayerVisible(id, visible)` and `setHeatVisible(id, visible)`: toggle layer on map, respect parent-hides-child rule
- [ ] 2.7 Write `reorder(newOrder)`: update `_order`, call `_assignPaneZIndices()`
- [ ] 2.8 Write `getFeatureLayers()`: return flat `[{layer, sid, question, color}]` array across all slots
- [ ] 2.9 Instantiate `window.layerManager = new LayerManager()`, call `.init(map, geoData, colors)`, remove old globals (`geoFeatureLayers`, `geoQuestionVisible`, `geoGroup`)

## 3. Legend Rewrite

- [ ] 3.1 Rewrite `LegendControl.onAdd()`: per question — `.geo-legend-item[data-layer-id]` with drag handle, checkbox, swatch, label, zoom icon inside `.geo-legend-row`
- [ ] 3.2 Add `.geo-legend-subitem` with heatmap checkbox + gradient swatch for Point-type questions only
- [ ] 3.3 Wire checkbox handlers: layer checkbox → `layerManager.setLayerVisible()` + FilterManager updates; heat checkbox → `layerManager.setHeatVisible()`
- [ ] 3.4 Wire zoom-to-layer click on label/crosshairs (same logic as current)
- [ ] 3.5 Init SortableJS on legend body: `handle: '.geo-drag-handle'`, `draggable: '.geo-legend-item'`, `onEnd` reads new order from DOM, re-inserts sub-items after parents, calls `layerManager.reorder()`

## 4. FilterManager Integration

- [ ] 4.1 Replace `_updateGeoMap()` body with `if (window.layerManager) window.layerManager.setFilter(this._mapSids)`
- [ ] 4.2 Replace `window.geoFeatureLayers` in `_updateGeoMapSelection()` with `window.layerManager ? window.layerManager.getFeatureLayers() : []`
- [ ] 4.3 Replace `window.geoFeatureLayers` in `draw:created` handler with `layerManager.getFeatureLayers()`
- [ ] 4.4 Remove old legend checkbox handler that called `window.geoQuestionVisible.set()` directly

## 5. Verification

- [ ] 5.1 Test: points render as before (color, click, selection, draw-select)
- [ ] 5.2 Test: heatmap checkbox toggles heatmap on/off independently from points
- [ ] 5.3 Test: cross-filtering (choice click) updates heatmap density
- [ ] 5.4 Test: drag-reorder in legend changes z-order on map
- [ ] 5.5 Test: hiding parent layer also hides its heatmap
- [ ] 5.6 Test: survey with no geo questions — no errors
- [ ] 5.7 Test: survey with only line/polygon questions — no heatmap sub-items in legend
