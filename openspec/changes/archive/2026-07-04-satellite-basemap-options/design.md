## Context

All 4 Leaflet maps (respondent, editor map picker, analytics, session mini-map) use a single global `MAPBOX_URL` from settings.py, injected via context processor. No `L.control.layers` exists anywhere. Map settings (position, zoom, geolocation) live on SurveySection; survey-wide settings live on SurveyHeader.

## Goals / Non-Goals

**Goals:**
- Per-survey basemap selection (which layers respondents can switch between)
- Reusable JS partial for all 4 maps — no copy-paste
- L.control.layers in top-right when >1 basemap enabled
- Backward compatible: existing surveys default to streets

**Non-Goals:**
- Per-section basemap override (one setting per survey is enough)
- Street view integration (separate feature)
- Custom WMS/WFS layers (separate backlog item)
- Basemap selection by respondent persisted across sections

## Decisions

### 1. Field on SurveyHeader, not SurveySection

**Decision**: `SurveyHeader.basemaps` JSONField storing a list of slugs, e.g. `["streets", "satellite"]`.

**Rationale**: Basemap choice is a survey-wide presentation setting, not a per-section map parameter. It groups naturally with `available_languages` and `thanks_html` on SurveyHeader. Editor UI lives in survey settings page, not the per-section map picker modal.

### 2. Three tile providers, no API keys for satellite/topo

**Decision**:
- `streets`: current Mapbox URL from `settings.MAPBOX_URL` + `settings.MAPBOX_ACCESS_TOKEN`
- `satellite`: Esri World Imagery `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
- `topo`: OpenTopoMap `https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png`

**Rationale**: Esri World Imagery and OpenTopoMap are free for non-commercial/low-volume use, no API key required. Covers the three most-requested use cases (urban, nature/rural, terrain).

### 3. Reusable partial `partials/basemap_layers.html`

**Decision**: Single Django template partial containing an IIFE that reads `map` from JS scope and `{{ survey.basemaps|safe }}` from template context. Creates tile layers, adds first to map, adds `L.control.layers` if >1.

**Rationale**: All 4 maps need the same logic. An `{% include %}` is simpler than a JS module (no build step, no new static files). The partial runs inside the calling template's JS scope, reading `map`, `mapboxUrl`, `mapboxAccessToken` as closure variables.

### 4. Fallback behavior

**Decision**: If `basemaps` is empty/null/missing, JS defaults to `["streets"]`.

**Rationale**: All existing surveys have `basemaps=[]` (JSONField default=list). They must continue showing the streets basemap without migration.

### 5. L.control.layers only when >1 basemap

**Decision**: If only 1 basemap is enabled, add it directly to map without a layer control. If >1, add `L.control.layers` with `collapsed: true` in top-right.

**Rationale**: A layer control with a single entry is noise. `collapsed: true` keeps the map clean — expands on hover/click.

## Component Design

### Reusable partial: `partials/basemap_layers.html`

```javascript
(function() {
    var _enabled = {{ survey.basemaps|safe }};
    if (!_enabled || !_enabled.length) _enabled = ['streets'];

    var _providers = {
        'streets':   { name: 'Streets',   url: mapboxUrl, opts: { attribution: '&copy; OpenStreetMap', maxZoom: 23, accessToken: mapboxAccessToken }},
        'satellite': { name: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', opts: { attribution: '&copy; Esri', maxZoom: 19 }},
        'topo':      { name: 'Topo',      url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', opts: { attribution: '&copy; OpenTopoMap', maxZoom: 17 }}
    };

    var _baseMaps = {};
    var _first = null;
    _enabled.forEach(function(slug) {
        var p = _providers[slug];
        if (!p) return;
        var layer = L.tileLayer(p.url, p.opts);
        _baseMaps[p.name] = layer;
        if (!_first) { _first = layer; _first.addTo(map); }
    });

    if (Object.keys(_baseMaps).length > 1) {
        L.control.layers(_baseMaps, null, { position: 'topright', collapsed: true }).addTo(map);
    }
})();
```

### Editor UI: checkbox picker in survey_settings.html

Hidden input `id_basemaps` holds JSON array. Checkboxes sync to it via inline JS. If nothing checked, defaults to `["streets"]`.
