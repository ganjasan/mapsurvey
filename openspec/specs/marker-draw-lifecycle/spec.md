# Marker Draw Lifecycle Specification

## Purpose
How drawing a geometry begins and ends: draw mode is single-shot for every geometry type, only one feature may be in edit mode at a time, and mode cleanup stays idempotent.
## Requirements
### Requirement: Single-shot draw mode for all geometry types
When a user activates a draw tool (point, line, or polygon) and completes drawing a feature, the draw handler SHALL be disabled immediately. The user MUST click the draw button again to place another feature.

#### Scenario: Point marker placed on desktop disables draw tool
- **WHEN** a desktop user clicks `.drawpoint` and clicks the map to place a marker
- **THEN** `currentDrawFeature.disable()` SHALL be called and `currentDrawFeature` SHALL be set to `null` before the popup opens

#### Scenario: Line drawn disables draw tool
- **WHEN** a user completes drawing a line (`.drawline`)
- **THEN** the `L.Draw.Polyline` handler SHALL be disabled in the `draw:created` handler

#### Scenario: Polygon drawn disables draw tool
- **WHEN** a user completes drawing a polygon (`.drawpolygon`)
- **THEN** the `L.Draw.Polygon` handler SHALL be disabled in the `draw:created` handler

#### Scenario: User cannot spam-click markers
- **WHEN** a user has just placed a marker and the draw handler has been disabled
- **THEN** clicking on the map SHALL NOT create additional markers

### Requirement: Single-edit mode enforcement
Only one map feature SHALL be in edit mode at any time. Starting to edit a new feature SHALL finish editing the previous one.

#### Scenario: Starting edit while another feature is being edited
- **WHEN** a user opens a popup on feature B and clicks "Edit" while feature A is already in edit mode
- **THEN** feature A's editing SHALL be disabled before feature B enters edit mode

#### Scenario: Dedicated edit layer tracking
- **WHEN** a feature enters edit mode via `startEditMode`
- **THEN** the system SHALL track the edited layer in a dedicated `currentEditLayer` variable, separate from `currentDrawFeature`

#### Scenario: End edit mode cleans up tracked layer
- **WHEN** the user finishes editing (clicks "Finish editing" button)
- **THEN** `currentEditLayer.editing.disable()` SHALL be called and `currentEditLayer` SHALL be set to `null`

### Requirement: Draw mode cleanup on feature creation
The `draw:created` event handler SHALL disable the draw handler as its first action, before any popup or layer operations.

#### Scenario: Draw handler disabled before popup opens
- **WHEN** `draw:created` fires for any geometry type
- **THEN** the draw handler referenced by `currentDrawFeature` SHALL be disabled and nulled before `editableLayers.addLayer()` or `layer.openPopup()` are called

### Requirement: endDrawMode remains idempotent
Calling `endDrawMode()` when no draw handler is active SHALL be a safe no-op.

#### Scenario: endDrawMode called with null currentDrawFeature
- **WHEN** `endDrawMode()` is called and `currentDrawFeature` is already `null`
- **THEN** the function SHALL complete without error, toggling only the UI (info panel, drawbar)

### Requirement: The respondent map is never driven while it has no size
The respondent page SHALL NOT ask Leaflet to move the map while its container has zero size.
Leaflet derives every projection from `map.getSize()`, so a move against a hidden container
unprojects to `LatLng(NaN, NaN)` and throws — once per frame for an animated fly. A `form` section
hides the map through the `survey-form-layout` body class, which makes this reachable in ordinary
use.

#### Scenario: A geolocation result arriving on a form section does not throw
- **WHEN** the geolocation callback returns while the respondent is on a section whose layout hides the map
- **THEN** no map move is attempted and no error is raised

#### Scenario: The deferred location is applied when the map returns
- **WHEN** the respondent moves to a section that shows the map again and that section declares no position of its own
- **THEN** the location that arrived while the map was hidden is applied

#### Scenario: A section's own position wins over a deferred location
- **WHEN** the section that brings the map back declares its own start position
- **THEN** that position is used and the deferred location is dropped, because an explicit section view outranks a stale locate request

#### Scenario: Non-finite coordinates are ignored
- **WHEN** a move is requested with a coordinate or zoom that is not a finite number
- **THEN** the move is skipped rather than passed to Leaflet

#### Scenario: An ordinary section transition still moves the map
- **WHEN** the respondent advances to a visible map section with its own position
- **THEN** the map flies to that position as before

