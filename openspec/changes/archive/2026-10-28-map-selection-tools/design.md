## Context

Analytics map has click-to-select (single session) with FilterManager.geoSelection. Features stored in flat `window.geoFeatureLayers` array. Leaflet 1.4.0 loaded, Leaflet.draw 1.0.4 available via CDN but not loaded on editor pages.

## Goals / Non-Goals

**Goals:**
- QGIS-style toolbar: Pointer, Rectangle, Polygon, Details
- Rectangle/Polygon select features within drawn shape, cross-filter all charts
- Ctrl+click multi-select in Pointer mode
- Session details modal with all answers + mini-map
- Auto-revert to Pointer after area select

**Non-Goals:**
- True freehand/lasso drawing
- Image rendering in details modal

## Decisions

### 1. Toolbar as L.Control at topright
**Choice**: Leaflet custom control with 4 icon buttons.
**Why**: Matches existing legend control pattern. No layout changes needed.

### 2. L.Draw.Rectangle and L.Draw.Polygon handlers
**Choice**: Create handler instances once, enable/disable on tool switch.
**Why**: Avoids recreating handlers on each switch. Only one active at a time.

### 3. Feature intersection approach
**Choice**: `bounds.contains(getLatLng())` for points, `bounds.intersects(getBounds())` for lines/polygons. For polygon select: `L.GeometryUtil.isMarkerInsidePolygon` for points.
**Why**: Simple, performant. Bounding-box intersection for non-point features is approximate but acceptable.

### 4. Ctrl+click via toggleGeoSid()
**Choice**: New FilterManager method that toggles a single sid in/out of geoSelection.
**Why**: Clean separation from setGeoSelection (replace all) vs toggle (add/remove one).

### 5. Session details via HTMX + Bootstrap modal
**Choice**: New server endpoint returns HTML partial, loaded into modal body.
**Why**: Matches existing HTMX patterns (text answers). Modal body includes mini-map initialized on show.

### 6. Mini-map timing
**Choice**: Check if modal is already visible; if so init immediately, else register one-time shown.bs.modal handler.
**Why**: HTMX swaps content into already-visible modal — shown event won't re-fire.
