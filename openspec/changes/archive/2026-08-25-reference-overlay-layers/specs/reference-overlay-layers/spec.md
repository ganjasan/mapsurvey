# reference-overlay-layers Specification

## ADDED Requirements

### Requirement: Creator uploads and configures a reference layer
An owner SHALL be able to upload a GeoJSON file (≤10 MB, WGS84, ≤5000 features,
≤5 layers per survey) that becomes a `SurveyMapLayer` with configurable name, color
(`#RRGGBB`), label field, key field, and info-popups flag. The stored GeoJSON SHALL be
the re-serialized parse of the upload, never the raw bytes. Upload SHALL return the
union of feature property names so label/key fields are picked from a dropdown, not
typed. Invalid files SHALL be rejected with a human-readable reason.

#### Scenario: Successful upload
- **WHEN** the owner uploads a valid 148 KB FeatureCollection of 35 zone polygons
- **THEN** a layer is created, the response lists its property names, and the editor card shows name, feature count and size

#### Scenario: Projected-CRS file rejected
- **WHEN** an uploaded file contains coordinates outside lng [-180,180] / lat [-90,90]
- **THEN** the upload is rejected with a message pointing at a non-WGS84 coordinate system

#### Scenario: Oversized file rejected
- **WHEN** the upload exceeds 10 MB
- **THEN** it is rejected before full processing with a size message

#### Scenario: Non-owner cannot manage layers
- **WHEN** a user without the owner role POSTs to any layer endpoint
- **THEN** the request is refused

### Requirement: Respondent map renders reference layers beneath answers
On map-layout sections, the respondent map SHALL render the survey's reference layers
in a dedicated pane below answer geometry. Feature styling SHALL honor simplestyle
properties (`stroke`, `fill`, `stroke-width`, `marker-color`, `stroke-opacity`,
`fill-opacity`) with the layer color as fallback; point features SHALL render as small
circle markers, not default markers. When a label field is set, features SHALL show a
permanent centered label with the property value HTML-escaped. Layers SHALL persist
across HTMX section navigation without refetching.

#### Scenario: Zones visible under observation markers
- **WHEN** a volunteer places observation points on a section whose survey has a zones layer
- **THEN** the zone polygons render beneath the markers, styled with the layer color and labeled from the label field

#### Scenario: Self-styled plan wins over layer color
- **WHEN** a layer's features carry simplestyle properties (e.g. green lawn, orange playground)
- **THEN** each feature renders in its own colors and the layer color is unused

#### Scenario: Label values are escaped
- **WHEN** a feature's label property contains `<img onerror=...>`
- **THEN** the label displays the literal text and no HTML executes

#### Scenario: Layers survive section navigation
- **WHEN** the respondent moves to the next section via HTMX
- **THEN** visible layers remain on the map without a new fetch of layer geometry

### Requirement: Reference layers never intercept answering
Reference-layer features SHALL NOT be selectable, editable, or draggable by
respondents. With info popups disabled the layer SHALL be fully non-interactive. With
info popups enabled, clicking a feature SHALL show an escaped read-only popup of its
name/description properties, and placing answer geometry by tapping the map SHALL
continue to work over layer features.

#### Scenario: Tap over a zone places the answer
- **WHEN** a respondent in point-placement mode taps inside a zone polygon (popups disabled)
- **THEN** an answer point is placed exactly as on bare map

#### Scenario: Popup shows plan details
- **WHEN** popups are enabled and a respondent clicks the "playground" polygon outside placement mode
- **THEN** a popup shows the feature's escaped name/description and the geometry cannot be modified

### Requirement: Layer visibility is controllable per section and by the respondent
Each section SHALL be able to hide any subset of the survey's layers
(`hidden_layers`; default — all visible; unknown IDs ignored). The respondent SHALL be
able to toggle each visible layer via the Leaflet layers control, which SHALL appear
whenever at least one reference layer is visible. Form-layout sections render no map
and therefore no layers.

#### Scenario: Section hides a layer
- **WHEN** a section lists a layer in `hidden_layers` and the respondent navigates to it
- **THEN** that layer is removed from the map and re-added on a section where it is not hidden

#### Scenario: Respondent toggles a layer off
- **WHEN** the respondent unchecks the layer in the layers control
- **THEN** the overlay disappears; answer geometry is unaffected

### Requirement: Layer geometry is served by a gated cacheable endpoint
Layer GeoJSON SHALL be served at `GET /surveys/<uuid>/layers/<id>.geojson` under the
same access rules as the survey's section pages, with an `ETag` derived from the
layer's `updated_at` and private caching. Layer GeoJSON SHALL NOT be inlined into the
respondent HTML and SHALL NOT be exposed at a public storage URL.

#### Scenario: Draft survey layer hidden from outsiders
- **WHEN** an anonymous request fetches a layer of an unpublished survey without a test link
- **THEN** the endpoint refuses as the survey page itself would

#### Scenario: Conditional revalidation
- **WHEN** a client re-requests with a matching `If-None-Match`
- **THEN** the endpoint returns 304 with no body

### Requirement: Feature kill switch
With `MAP_REFERENCE_LAYERS` off, the editor SHALL NOT render layer management UI, the
respondent page SHALL receive no layer metadata, and layer endpoints SHALL return 404.
Stored layers SHALL be preserved.

#### Scenario: Flag off hides everything, loses nothing
- **WHEN** the flag is turned off and later on again
- **THEN** no layer surface renders while off, and all layers reappear unchanged after
