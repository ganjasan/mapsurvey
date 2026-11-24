## MODIFIED Requirements

### Requirement: Creator uploads and configures a reference layer
A survey owner SHALL be able to add a reference layer to a survey by
uploading a GeoPackage, zipped shapefile, KML, GeoJSON or CSV with coordinate columns (≤10 MB,
≤5000 features, ≤10 layers per survey) from the section's Map card or from Survey settings. The
upload SHALL go through the Data import: a file in a projected coordinate system SHALL be
reprojected to WGS 84 (a CSV as the Data import reads it), never refused for its projection. The
result SHALL be a workspace layer dataset (`public`, so respondents can see it) linked to the
canonical survey and placed with scope `all`; the layer SHALL have a configurable name, color
(`#RRGGBB`), label field, key field, and info-popups flag. The stored GeoJSON SHALL be derived from
the layer's objects (never the raw upload bytes). The upload SHALL be parsed into a feature tree
exactly once, objects SHALL be written in batches, and the derived GeoJSON SHALL be assembled one
feature at a time rather than from a whole-collection tree. The union of feature property names
SHALL be stored on the layer when it is rebuilt and returned by the upload so label/key fields are
picked from a dropdown, not typed; no editor surface SHALL parse the stored GeoJSON to list property
names. Invalid files SHALL be rejected with a human-readable reason. Survey settings SHALL list the
survey's layers as "Layers used here" with where each shows (scope, changeable there as in the Map
card), *Open in Data* and *Remove from this survey* (unlink and unplace; the dataset stays in Data),
and SHALL offer *+ Layer* (upload or From Data), which places the layer with scope `all`.

#### Scenario: Successful upload
- **WHEN** the editor uploads a valid 148 KB FeatureCollection of 35 zone polygons
- **THEN** a layer dataset is created, linked and placed on every map section, the response lists its property names, and the Map card shows name, feature count and scope

#### Scenario: Property names come from the layer, not a parse
- **WHEN** the editor renders the settings card for a survey with a 10 MB layer
- **THEN** the card lists the layer's property names without selecting or parsing the stored GeoJSON

#### Scenario: Derived GeoJSON is unchanged by the streaming assembly
- **WHEN** a layer with categories, cover images and reserved properties is rebuilt
- **THEN** the stored FeatureCollection is byte-identical to the previous whole-tree serialisation

#### Scenario: Projected-CRS file is reprojected
- **WHEN** an uploaded GeoJSON declares NAD83 Georgia West (US feet)
- **THEN** its objects are stored at the matching WGS 84 positions and the dialog says the coordinates were converted

#### Scenario: Oversized file rejected
- **WHEN** the upload exceeds 10 MB
- **THEN** it is rejected before full processing with a size message

#### Scenario: Viewer cannot manage layers
- **WHEN** a user with only the `viewer` role POSTs to any layer endpoint
- **THEN** the request is refused

#### Scenario: Remove from this survey
- **WHEN** the owner removes a layer from the survey in "Layers used here"
- **THEN** the survey no longer links or places it and the dataset is still listed in Data

### Requirement: Layer visibility is controllable per section and by the respondent
A layer SHALL appear on a section's map if and only if a placement of the survey covers that section
(spec `map-layer-placement`); layers SHALL render in placement order. An "Objects on the map"
question SHALL NOT by itself put a layer on a map. Sections SHALL NOT carry a separate visibility
list. The respondent SHALL be able to toggle each visible layer via the Leaflet layers control and
the panel legend, which SHALL appear whenever at least one layer is on the map. Form-layout sections
render no map and therefore no layers.

#### Scenario: Layer shown through a placement
- **WHEN** "existing-dog-bins" is placed on section A only
- **THEN** the layer renders on A's map and not on B's

#### Scenario: Question removed
- **WHEN** the creator deletes the only Objects question asking about a placed layer
- **THEN** the layer stays on the section's map

#### Scenario: Respondent toggles a layer off
- **WHEN** the respondent unchecks the layer in the layers control
- **THEN** the overlay disappears; answer geometry is unaffected

### Requirement: The editor preview renders reference layers
The editor's Live preview SHALL render exactly the layers placed on the previewed section and the
survey's study area, from the same metadata builder the respondent page uses, so the preview never
shows a layer the respondent will not see.

#### Scenario: Preview after placing a layer
- **WHEN** the creator uploads a layer from the Map card and the preview refreshes
- **THEN** the layer appears on the preview map and in the panel legend

#### Scenario: Kill switch applies to the preview too
- **WHEN** `MAP_REFERENCE_LAYERS` is off
- **THEN** the preview carries no layer config
