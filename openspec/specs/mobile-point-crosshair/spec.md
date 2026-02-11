## ADDED Requirements

### Requirement: Touch device detection
The system SHALL use crosshair mode for point placement on ALL devices, regardless of pointer type. The `window.matchMedia('(pointer: coarse)')` check SHALL NOT be used to gate crosshair mode activation.

#### Scenario: Fine pointer device uses crosshair mode
- **WHEN** a user on a device with `pointer: fine` clicks a point draw button (`.drawpoint`)
- **THEN** the system SHALL enter crosshair mode (same as touch devices)

#### Scenario: Coarse pointer device uses crosshair mode
- **WHEN** a user on a device with `pointer: coarse` clicks a point draw button (`.drawpoint`)
- **THEN** the system SHALL enter crosshair mode

#### Scenario: L.Draw.Marker is not used for point placement
- **WHEN** any user clicks a point draw button (`.drawpoint`)
- **THEN** the system SHALL NOT instantiate `L.Draw.Marker`; crosshair mode SHALL be the sole point-placement mechanism

### Requirement: Crosshair overlay display
When crosshair mode is active, the system SHALL display a fixed overlay centered on the map screen. The overlay SHALL render a pin-shaped marker (SVG teardrop, identical to the Leaflet FontAwesome marker shape) filled with the question's color, with the question's FontAwesome icon (from `data-icon`) centered inside the pin in white. The overlay container SHALL have `pointer-events: none` so the map remains pannable underneath.

#### Scenario: Entering crosshair mode
- **WHEN** a user clicks a `.drawpoint` button
- **THEN** on mobile viewports (max-width 768px) the info panel SHALL slide out; on desktop the info panel SHALL remain visible. A crosshair overlay SHALL appear at the center of the map showing a pin marker in the question's color with the question's icon inside.

#### Scenario: Map remains pannable during crosshair mode
- **WHEN** crosshair mode is active and the user pans the map
- **THEN** the map SHALL pan normally and the pin marker SHALL remain fixed at the center of the screen

### Requirement: Apply action places marker
The crosshair overlay SHALL display an Apply button (green, checkmark icon). Pressing Apply SHALL place a marker at the current map center coordinates. The marker popup SHALL use a unique form ID consistent with the marker-popup-isolation capability.

#### Scenario: User applies point placement
- **WHEN** the user presses the Apply button during crosshair mode
- **THEN** the system SHALL create an `L.marker` at `map.getCenter()` with the question's icon and color, fire `draw:created`, and hide the crosshair overlay. The `draw:created` handler SHALL disable any active draw handler (per marker-draw-lifecycle) and bind a popup with a unique form ID (per marker-popup-isolation).

#### Scenario: Apply with sub-questions opens popup
- **WHEN** the user presses Apply and the question has sub-questions
- **THEN** the marker SHALL be placed and its sub-question popup SHALL open

#### Scenario: Apply without sub-questions returns to info panel
- **WHEN** the user presses Apply and the question has no sub-questions
- **THEN** the marker SHALL be placed, crosshair mode SHALL exit, and on mobile the info panel SHALL slide back in

### Requirement: Cancel action discards placement
The crosshair overlay SHALL display a Cancel button (red, X icon). Pressing Cancel SHALL discard the placement without creating a marker.

#### Scenario: User cancels point placement
- **WHEN** the user presses the Cancel button during crosshair mode
- **THEN** no marker SHALL be placed, crosshair mode SHALL exit, and on mobile the info panel SHALL slide back in

### Requirement: Action buttons are touch-accessible
The Apply and Cancel buttons SHALL have `pointer-events: auto` and a minimum touch target height of 48 pixels. They SHALL be rectangular with rounded corners, positioned at the bottom of the screen with fixed positioning. Each button SHALL display an icon and a text label.

#### Scenario: Buttons are tappable while map is pannable
- **WHEN** crosshair mode is active
- **THEN** the Apply and Cancel buttons SHALL respond to taps at the bottom of the screen, while touches on other areas of the overlay SHALL pass through to the map

### Requirement: Only point questions use crosshair mode
Crosshair mode SHALL apply only to `point` type questions (`.drawpoint` buttons). Line (`.drawline`) and polygon (`.drawpolygon`) questions SHALL continue using their existing drawing behavior regardless of pointer type.

#### Scenario: Line drawing on any device
- **WHEN** a user clicks a `.drawline` button
- **THEN** the system SHALL use the standard `L.Draw.Polyline` behavior (no crosshair)

#### Scenario: Polygon drawing on any device
- **WHEN** a user clicks a `.drawpolygon` button
- **THEN** the system SHALL use the standard `L.Draw.Polygon` behavior (no crosshair)

### Requirement: Info panel partial width on mobile
On mobile viewports (max-width 768px), the info panel SHALL NOT cover 100% of the screen width. It SHALL occupy 85% width, leaving a visible strip of the map on the right edge so users can see there is a map behind it.

#### Scenario: Info panel on mobile shows map edge
- **WHEN** the info panel is visible on a mobile device
- **THEN** the panel SHALL occupy 85% of the screen width, and approximately 15% of the map SHALL be visible on the right

### Requirement: Info panel slide animation on mobile
On mobile viewports (max-width 768px), the info panel SHALL animate when showing and hiding. It SHALL use a CSS `transform: translateX()` slide transition (0.3s ease). When hidden, the panel SHALL slide fully off-screen to the left. When shown, it SHALL slide back to its original position. On desktop viewports, the info panel SHALL remain permanently visible and not respond to show/hide toggles.

#### Scenario: Hiding info panel animates on mobile
- **WHEN** the info panel is hidden on a mobile viewport (e.g., user clicks close or enters draw mode)
- **THEN** the panel SHALL slide to the left over 0.3 seconds

#### Scenario: Showing info panel animates on mobile
- **WHEN** the info panel is shown on a mobile viewport (e.g., user clicks show button or exits draw mode)
- **THEN** the panel SHALL slide in from the left over 0.3 seconds

#### Scenario: Info panel stays visible on desktop
- **WHEN** the user enters draw mode on a desktop viewport (wider than 768px)
- **THEN** the info panel SHALL remain visible and not hide

### Requirement: Data format unchanged
Markers placed via crosshair mode SHALL produce the same GeoJSON data format in the hidden `.geo-inp` input as markers placed via the standard `L.Draw.Marker` flow. No backend changes are required.

#### Scenario: Submitted geo data is identical
- **WHEN** a marker is placed via crosshair mode and the form is submitted
- **THEN** the hidden input SHALL contain pipe-delimited GeoJSON with `feature.properties.question_id` set, identical in format to markers placed via standard mode
