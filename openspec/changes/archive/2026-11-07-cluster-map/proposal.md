## Why

A university research office asked (by email, 2026-11-06, #563) whether Pro has a *cluster map*. They collect one point per research site, worldwide, and want nearby points to merge into a counted circle that splits as you zoom in. Mapsurvey draws plain markers and a heat map, nowhere clusters. Points spread over continents overlap into a smear as markers, and a heat map hides the count the reader came for.

## What Changes

- **Responses → Map pane**: the layer menu of a Point layer offers *Create Clusters* next to *Create Heatmap*. It adds a derived `cluster` slot to the `LayerManager` (the heat/coverage model: own row under the source, own pane, follows the session filter and visibility, removable). Creating it hides the source layer, because clusters drawn over the same points read as double; removing it shows the source again. A single point inside the cluster layer behaves like a source point: click selects the session and opens the attribute popup.
- **Public results**: a `map` block's visualisation gets a third value, `cluster` (*Clusters*), next to `auto` (Markers) and `heatmap`. Point answers are drawn in a cluster group; lines and polygons render as shapes as before; popups carry the same creator-selected fields.
- Library: Leaflet.markercluster 1.5.3 from unpkg (the host the other Leaflet assets on these pages come from), compatible with our Leaflet 1.4.0.
- Every plan, like the heat map. Not a Pro feature.

## Capabilities

### New Capabilities
- `responses-cluster-map`: Point answer layers on the Responses Map pane can be shown as clusters.

### Modified Capabilities
- `public-results-page`: the map block's visualisation adds `cluster`.

## Impact

- `survey/templates/editor/partials/analytics_geo_map.html` (LayerManager, Layers panel, layer menu), `survey/templates/editor/analytics_dashboard_v2.html` (plugin include).
- `survey/templates/public_results.html` (`renderMap`, plugin include), `survey/public_results_editor.py` (`map_viz_options`).
- No model, migration, API or export change: `PublicResultsBlock.viz` is free text already.
