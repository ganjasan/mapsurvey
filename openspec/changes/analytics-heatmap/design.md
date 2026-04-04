# Design: Heatmap Sub-Layers

## Architecture

### LayerManager

Singleton object replacing `window.geoFeatureLayers`, `window.geoQuestionVisible`, `window.geoGroup`.

```
LayerManager {
    _map:    L.Map
    _slots:  Map<questionName, LayerSlot>
    _order:  [questionName, ...]   // legend order = z-order (index 0 = bottom)
    _sids:   Set<number> | null    // current cross-filter
    _BASE_Z: 400
    _STEP:   10
}

LayerSlot {
    id:           string            // question name
    geomType:     string            // 'Point' | 'LineString' | 'Polygon'
    color:        string
    pane:         string            // 'geo-pane-0'
    heatPane:     string | null     // 'geo-heat-0' (Point only)
    visible:      boolean           // points layer toggle
    heatVisible:  boolean           // heatmap toggle (Point only)
    features:     [{layer, sid}]    // individual Leaflet layers
    allPoints:    [[lat, lng]]      // precomputed (Point only)
    heatLayer:    L.HeatLayer|null  // (Point only)
}
```

### Public API

- `init(map, geoData, colors)` — build slots, create panes, create features and heat layers
- `setFilter(sids)` — update visibility per `_mapSids`, rebuild active heatmaps
- `setLayerVisible(id, visible)` — toggle point layer (also hides heat if parent hidden)
- `setHeatVisible(id, visible)` — toggle heatmap sub-layer
- `reorder(newOrder)` — update `_order`, reassign pane z-indices
- `getFeatureLayers()` — flat `[{layer, sid, question, color}]` for backward compat
- `getSlotIds()` — ordered list of question names

### z-Order via Map Panes

Each slot gets a dedicated pane pair:
```
geo-pane-0     zIndex = 400   (points, bottom of stack)
geo-heat-0     zIndex = 401   (heat, just above its points)
geo-pane-1     zIndex = 410
geo-heat-1     zIndex = 411
```

Reorder only changes `pane.style.zIndex`. No layer add/remove.

### Heatmap Lifecycle

1. **Create** at init: `L.heatLayer([], { radius: 20, blur: 25, max: 1.0, pane: heatPane })` — empty, not added to map
2. **Toggle on**: `_rebuildHeat(slot)` then `map.addLayer(slot.heatLayer)`
3. **Filter change**: if visible, call `_rebuildHeat(slot)` which filters `slot.features` by `_sids`, extracts coords, calls `setLatLngs()`
4. **Toggle off**: `map.removeLayer(slot.heatLayer)`

### Legend UI

```
[≡] [✓] ● Question A        [⌖]
       [✓] 🌈 Heatmap
[≡] [✓] ● Question B (line)  [⌖]
```

- `[≡]` = drag handle (SortableJS)
- `[✓]` = visibility checkbox
- `●` = color swatch
- `[⌖]` = zoom to layer
- Sub-item indented, only for Point questions
- `🌈` = gradient swatch (CSS linear-gradient)
- SortableJS `draggable: '.geo-legend-item'`, sub-items move with parent via `onEnd` DOM reorder

### FilterManager Integration

- `_updateGeoMap()` → `layerManager.setFilter(this._mapSids)`
- `_updateGeoMapSelection()` → iterates `layerManager.getFeatureLayers()` for style updates
- `draw:created` handler → iterates `layerManager.getFeatureLayers()` for spatial selection
- Register no new components — LayerManager is called directly from existing hooks

### Plugin

- Leaflet.heat 0.2.0 from unpkg CDN, loaded after leaflet.draw in `extra_head`
- SortableJS 1.15.0 already in editor_base.html
