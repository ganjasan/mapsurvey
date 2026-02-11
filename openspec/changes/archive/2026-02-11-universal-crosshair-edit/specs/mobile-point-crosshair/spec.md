## MODIFIED Requirements

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

### Requirement: Only point questions use crosshair mode
Crosshair mode SHALL apply only to `point` type questions (`.drawpoint` buttons). Line (`.drawline`) and polygon (`.drawpolygon`) questions SHALL continue using their existing drawing behavior regardless of pointer type.

#### Scenario: Line drawing on any device
- **WHEN** a user clicks a `.drawline` button
- **THEN** the system SHALL use the standard `L.Draw.Polyline` behavior (no crosshair)

#### Scenario: Polygon drawing on any device
- **WHEN** a user clicks a `.drawpolygon` button
- **THEN** the system SHALL use the standard `L.Draw.Polygon` behavior (no crosshair)
