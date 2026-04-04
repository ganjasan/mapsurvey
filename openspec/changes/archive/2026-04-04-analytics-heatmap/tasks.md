## 1. Infrastructure

- [x] 1.1 Add `leaflet-heat.js` 0.2.0 CDN script tag to `analytics_dashboard.html`
- [x] 1.2 Add CSS rules for legend, drag handles, heatmap swatches, layer menu, settings popover, inline rename

## 2. LayerManager Implementation

- [x] 2.1 LayerManager constructor with `_slots` (Map), `_order`, `_sids`, `_paneCounter`, z-index constants
- [x] 2.2 `init(map, geoData, colors)`: build feature slots with per-question panes, features, allPoints
- [x] 2.3 `_assignPaneZIndices()`: top of legend = highest z-index (inverted order)
- [x] 2.4 `createHeat(sourceId)`: create independent heat slot with own pane, canvas in custom pane, initial render
- [x] 2.5 `removeHeat(heatId)`: remove canvas from DOM, delete slot from order
- [x] 2.6 `_rebuildHeat(slot)`: filter source features by `_sids`, setLatLngs, toggle `canvas.style.display`
- [x] 2.7 `setFilter(sids)`: update feature visibility + rebuild active heatmaps
- [x] 2.8 `setLayerVisible(id, visible)`: toggle features or heat layers
- [x] 2.9 `setHeatOptions(heatId, opts)`: update leaflet.heat options + redraw
- [x] 2.10 `reorder(newOrder)`, `getFeatureLayers()`, `getSlot()`, `hasHeatFor()`

## 3. Legend UI

- [x] 3.1 Toggle-all checkbox in legend header
- [x] 3.2 Feature layer items: drag handle, checkbox, swatch, label, zoom icon, menu button (Point only)
- [x] 3.3 Heat layer items: drag handle, checkbox, gradient swatch, renameable label, settings gear, delete button
- [x] 3.4 Layer context menu with "Create Heatmap" action
- [x] 3.5 SortableJS drag-and-drop reorder
- [x] 3.6 Inline rename via double-click on heat layer label

## 4. Heatmap Settings Popover

- [x] 4.1 Opens top-center of map, draggable by header
- [x] 4.2 Shows source layer name, close button
- [x] 4.3 Sliders for radius, blur, opacity with live update

## 5. FilterManager Integration

- [x] 5.1 `_updateGeoMap()` delegates to `layerManager.setFilter(_mapSids)`
- [x] 5.2 `_updateGeoMapSelection()` uses `layerManager.getFeatureLayers()`
- [x] 5.3 `draw:created` handler uses `layerManager.getFeatureLayers()`
- [x] 5.4 Skip detached layers in `_updateGeoMapSelection` (hasLayer guard)

## 6. Cleanup

- [x] 6.1 Remove geo questions from analytics stats sidebar (redundant with Response Map)
- [x] 6.2 Map container `z-index: 0` to create stacking context (prevent panes overlapping header)
- [x] 6.3 Remove old globals (`geoFeatureLayers`, `geoQuestionVisible`, `geoGroup`)
