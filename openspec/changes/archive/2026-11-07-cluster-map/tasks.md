## 1. Responses Map pane

- [x] 1.1 Load Leaflet.markercluster 1.5.3 (CSS + JS) on the Responses page
- [x] 1.2 `LayerManager`: `createClusters`, `removeClusters`, `hasClustersFor`, `_rebuildClusters`; filter and visibility reach the slot
- [x] 1.3 Creating clusters hides the source (row unticked); removing restores it
- [x] 1.4 Single points in the cluster layer: same click handler as source points
- [x] 1.5 Layers panel row (swatch, label, zoom, remove) and the *Create Clusters* menu entry for Point layers

## 2. Public results

- [x] 2.1 `map_viz_options` gains `('cluster', 'Clusters')`
- [x] 2.2 `renderMap` draws Point features in a cluster group in `cluster` mode; plugin loaded on the page

## 3. Tests and checks

- [x] 3.1 `survey/tests/test_responses_cluster_map.py` (new capability module)
- [x] 3.2 Public results tests: the option is offered and the page carries the cluster path
- [x] 3.3 Browser check on both surfaces with a seeded point survey
- [x] 3.4 Help centre: mention clusters where the heat map is described
