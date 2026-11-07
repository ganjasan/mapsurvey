## ADDED Requirements

### Requirement: Point answer layers can be shown as clusters

On the Responses Map pane, the layer menu of a `features` layer whose geometry is Point SHALL offer *Create Clusters* in addition to *Create Heatmap*. Creating clusters SHALL add a `cluster` slot to the `LayerManager`, listed in the Layers panel directly under its source layer and drawn in its own pane; the menu SHALL show *Clusters exist* while the slot exists. Nearby points SHALL be drawn as one circle in the source layer's colour carrying the number of points it holds, and SHALL split into smaller clusters and single points as the creator zooms in or clicks the circle. Line, polygon and spray layers SHALL NOT offer clusters.

#### Scenario: Point layer offers clusters
- **WHEN** a creator opens the layer menu of a point question layer
- **THEN** the menu offers "Create Clusters" next to "Create Heatmap"
- **AND** once created, a clusters row appears under the source row and the menu shows "Clusters exist"

#### Scenario: Shape layer does not offer clusters
- **WHEN** a creator opens the layer menu of a line or polygon question layer
- **THEN** the menu offers coverage only

### Requirement: The cluster layer replaces its source on the map until removed

Creating clusters SHALL hide the source layer and untick its row, because clusters drawn over the same points read as duplicates; the creator MAY tick the source back. Removing the clusters row SHALL show the source layer again. A single point in the cluster layer SHALL behave like a point of the source layer: a click in pointer mode selects that response and opens the attribute popup, a click in details mode opens the response.

#### Scenario: Source is hidden while clusters exist
- **WHEN** the creator creates clusters for a point layer
- **THEN** the source layer's points are no longer drawn and its checkbox is unticked

#### Scenario: Removing clusters restores the source
- **WHEN** the creator removes the clusters row
- **THEN** the source layer's points are drawn again and its checkbox is ticked

### Requirement: Clusters follow the response filter and visibility

The cluster slot SHALL count only the responses in the current selection or filter, and SHALL be rebuilt whenever the filter changes, through the same path heat slots are rebuilt. Unticking the clusters row SHALL remove the clusters from the map; ticking it SHALL draw them again for the current filter.

#### Scenario: Filter narrows the counts
- **WHEN** the creator filters the Responses page to a subset of responses
- **THEN** the cluster counts include only the points of those responses
