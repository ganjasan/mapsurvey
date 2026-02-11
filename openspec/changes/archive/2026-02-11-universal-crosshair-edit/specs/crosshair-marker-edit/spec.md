## ADDED Requirements

### Requirement: Crosshair-based marker repositioning
When the user clicks the "Edit" button in a point marker's popup, the system SHALL enter crosshair mode to allow repositioning the marker. The crosshair overlay SHALL display with the marker's color and icon. The map SHALL pan to center on the marker's current position.

#### Scenario: Edit button on point marker enters crosshair mode
- **WHEN** the user clicks the "Edit" button (`.layer-edit`) in a point marker's popup
- **THEN** the popup SHALL close, the map SHALL pan to the marker's current LatLng, the crosshair overlay SHALL appear with the marker's color and icon, and the original marker SHALL be hidden

#### Scenario: Edit button on line/polygon keeps existing behavior
- **WHEN** the user clicks the "Edit" button in a line or polygon feature's popup
- **THEN** the system SHALL call `startEditMode(layer)` as before (Leaflet drag handles, no crosshair)

### Requirement: Apply repositions the marker
When crosshair mode is active for repositioning and the user presses Apply, the system SHALL move the marker to the map center coordinates and restore its visibility.

#### Scenario: Apply moves marker to new position
- **WHEN** crosshair mode is active for an existing marker and the user presses the Apply button
- **THEN** the marker SHALL be moved to `map.getCenter()`, the marker SHALL become visible again, and the crosshair overlay SHALL hide

#### Scenario: Apply during edit does not create a new marker
- **WHEN** crosshair mode is active for an existing marker and the user presses Apply
- **THEN** the system SHALL NOT fire `draw:created` and SHALL NOT add a new layer to `editableLayers`

#### Scenario: Apply during edit preserves marker properties
- **WHEN** crosshair mode is active for an existing marker with sub-question properties and the user presses Apply
- **THEN** the marker's `feature.properties` SHALL remain unchanged (only the position changes)

### Requirement: Cancel restores original marker position
When crosshair mode is active for repositioning and the user presses Cancel, the system SHALL restore the marker to its original position and visibility without any changes.

#### Scenario: Cancel restores marker visibility
- **WHEN** crosshair mode is active for an existing marker and the user presses Cancel
- **THEN** the marker SHALL become visible again at its original position, and the crosshair overlay SHALL hide

#### Scenario: Cancel does not modify marker data
- **WHEN** crosshair mode is active for an existing marker and the user presses Cancel
- **THEN** the marker's LatLng and `feature.properties` SHALL remain unchanged

### Requirement: Info panel behavior during edit-mode crosshair
The info panel behavior during crosshair-based editing SHALL match the behavior during crosshair-based placement: on mobile the panel slides away, on desktop it remains visible.

#### Scenario: Mobile info panel hides during crosshair edit
- **WHEN** the user enters crosshair edit mode on a mobile viewport (max-width 768px)
- **THEN** the info panel SHALL slide out to the left

#### Scenario: Mobile info panel returns after crosshair edit Apply/Cancel
- **WHEN** the user presses Apply or Cancel during crosshair edit on a mobile viewport
- **THEN** the info panel SHALL slide back in

#### Scenario: Desktop info panel stays visible during crosshair edit
- **WHEN** the user enters crosshair edit mode on a desktop viewport (wider than 768px)
- **THEN** the info panel SHALL remain visible

### Requirement: State tracking for edit-mode crosshair
The system SHALL track which layer is being repositioned using a `crosshairEditLayer` variable. This variable SHALL be `null` when crosshair mode is used for new placement and SHALL reference the layer when used for repositioning.

#### Scenario: crosshairEditLayer is set during edit
- **WHEN** the user clicks "Edit" on a point marker and crosshair mode activates
- **THEN** `crosshairEditLayer` SHALL reference the layer being edited

#### Scenario: crosshairEditLayer is cleared after Apply
- **WHEN** the user presses Apply or Cancel during crosshair edit
- **THEN** `crosshairEditLayer` SHALL be set to `null`

#### Scenario: crosshairEditLayer is null during new placement
- **WHEN** the user clicks a `.drawpoint` button to place a new marker
- **THEN** `crosshairEditLayer` SHALL be `null` and the Apply action SHALL fire `draw:created`
