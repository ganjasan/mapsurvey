## MODIFIED Requirements

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
