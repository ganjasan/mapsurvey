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
