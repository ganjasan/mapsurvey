## ADDED Requirements

### Requirement: Touch device detection
The system SHALL detect whether the user's primary pointing device is coarse (finger) using `window.matchMedia('(pointer: coarse)')`. This detection SHALL determine whether crosshair mode is used for point placement.

#### Scenario: Coarse pointer device uses crosshair mode
- **WHEN** a user on a device with `pointer: coarse` clicks a point draw button (`.drawpoint`)
- **THEN** the system SHALL enter crosshair mode instead of activating `L.Draw.Marker`

#### Scenario: Fine pointer device uses standard mode
- **WHEN** a user on a device with `pointer: fine` clicks a point draw button (`.drawpoint`)
- **THEN** the system SHALL activate `L.Draw.Marker` as before (no crosshair)

### Requirement: Crosshair overlay display
When crosshair mode is active, the system SHALL display a fixed overlay centered on the map screen. The overlay SHALL contain the question's marker icon (from the button's `data-icon` attribute) rendered in the question's color (from `data-color`). The overlay container SHALL have `pointer-events: none` so the map remains pannable underneath.

#### Scenario: Entering crosshair mode
- **WHEN** a coarse-pointer user clicks a `.drawpoint` button
- **THEN** the info panel SHALL be hidden, and a crosshair overlay SHALL appear at the center of the map showing the question's icon in the question's color

#### Scenario: Map remains pannable during crosshair mode
- **WHEN** crosshair mode is active and the user pans the map
- **THEN** the map SHALL pan normally and the crosshair icon SHALL remain fixed at the center of the screen

### Requirement: Apply action places marker
The crosshair overlay SHALL display an Apply button (green, checkmark icon). Pressing Apply SHALL place a marker at the current map center coordinates.

#### Scenario: User applies point placement
- **WHEN** the user presses the Apply button during crosshair mode
- **THEN** the system SHALL create an `L.marker` at `map.getCenter()` with the question's icon and color, add it to `editableLayers` with `feature.properties.question_id` set, bind the sub-question popup, and hide the crosshair overlay

#### Scenario: Apply with sub-questions opens popup
- **WHEN** the user presses Apply and the question has sub-questions
- **THEN** the marker SHALL be placed and its sub-question popup SHALL open

#### Scenario: Apply without sub-questions returns to info panel
- **WHEN** the user presses Apply and the question has no sub-questions
- **THEN** the marker SHALL be placed, crosshair mode SHALL exit, and the info panel SHALL be shown

### Requirement: Cancel action discards placement
The crosshair overlay SHALL display a Cancel button (red, X icon). Pressing Cancel SHALL discard the placement without creating a marker.

#### Scenario: User cancels point placement
- **WHEN** the user presses the Cancel button during crosshair mode
- **THEN** no marker SHALL be placed, crosshair mode SHALL exit, and the info panel SHALL be shown

### Requirement: Action buttons are touch-accessible
The Apply and Cancel buttons SHALL have `pointer-events: auto` and a minimum touch target size of 44x44 pixels. They SHALL be positioned below the crosshair icon with sufficient spacing to avoid interfering with map panning.

#### Scenario: Buttons are tappable while map is pannable
- **WHEN** crosshair mode is active
- **THEN** the Apply and Cancel buttons SHALL respond to taps, while touches on other areas of the overlay SHALL pass through to the map

### Requirement: Only point questions use crosshair mode
Crosshair mode SHALL apply only to `point` type questions (`.drawpoint` buttons). Line (`.drawline`) and polygon (`.drawpolygon`) questions SHALL continue using their existing drawing behavior regardless of pointer type.

#### Scenario: Line drawing on touch device
- **WHEN** a coarse-pointer user clicks a `.drawline` button
- **THEN** the system SHALL use the standard `L.Draw.Polyline` behavior (no crosshair)

#### Scenario: Polygon drawing on touch device
- **WHEN** a coarse-pointer user clicks a `.drawpolygon` button
- **THEN** the system SHALL use the standard `L.Draw.Polygon` behavior (no crosshair)

### Requirement: Data format unchanged
Markers placed via crosshair mode SHALL produce the same GeoJSON data format in the hidden `.geo-inp` input as markers placed via the standard `L.Draw.Marker` flow. No backend changes are required.

#### Scenario: Submitted geo data is identical
- **WHEN** a marker is placed via crosshair mode and the form is submitted
- **THEN** the hidden input SHALL contain pipe-delimited GeoJSON with `feature.properties.question_id` set, identical in format to markers placed via standard mode
