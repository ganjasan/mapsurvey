## Context

The Responses Map pane draws each geo question as a `features` slot of the `LayerManager`; derived views (heat for points, coverage for shapes) are separate slots created from the layer menu. Selection, lasso and the session filter act on the source slot's own markers. The public results page renders a map block in `renderMap` with `L.geoJSON` and, for `heatmap`, `L.heatLayer`.

## Decisions

- **A derived slot, not a toggle on the source.** Clustering the source markers in place would put them inside a `MarkerClusterGroup`, which owns adding and removing its children: every path that adds or removes source markers (filter, visibility, selection highlight, lasso hit-testing) would have to learn it. A `cluster:<source>` slot holding its own `circleMarker`s (same colour, same click handler) leaves every source path as it is. Cost: two copies of each point in memory, trivial at survey scale.
- **Creating clusters hides the source; removing them restores it.** Heat is meant to be read over the points; clusters over the same points read as duplicates. The source row's checkbox is unticked, so the panel tells the truth, and the creator can tick it back.
- **Cluster icon** is a `divIcon` in the source colour with the count. Its HTML is built from a number and a palette colour only, never from respondent text. `showCoverageOnHover` is off (the hull polygon confuses more than it explains on a world map); `maxClusterRadius` 50 px; `chunkedLoading` on.
- **Filter** rebuilds the cluster group (`clearLayers` + `addLayers` of the entries whose session is in scope) at the same moment heat rebuilds.
- **Public page** keeps one code path: in `cluster` mode Point features are filtered out of the shapes layer and go into an `L.geoJSON` inside a `markerClusterGroup` with the same `onEachFeature`; bounds come from both layers.
- **unpkg, pinned 1.5.3**: Leaflet and leaflet.heat already load from unpkg on these pages; no CSP restricts script hosts.

## Risks

- Leaflet 1.4.0 with markercluster 1.5.3: the plugin's peer range is `^1.3.1`; verified in the browser on both surfaces.
