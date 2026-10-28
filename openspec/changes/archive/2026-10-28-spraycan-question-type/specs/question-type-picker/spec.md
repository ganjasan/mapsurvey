## ADDED Requirements

### Requirement: Spraycan is a map question in the picker

The type picker SHALL list `spraycan` in the map-questions group, labelled "Spray area", with a
spray-can icon, the hint "Respondent sprays a fuzzy area with a brush — density shows confidence" and
the same canned example the other map questions get (the paint-mode button as the respondent
sees it; the example frame has no map). The question modal SHALL show the Brush size control for this type and
hide the marker icon picker and min/max features; the live preview SHALL render the paint-mode
button as configured. The picker-metadata parity test SHALL cover the new type like any
other.

#### Scenario: Spraycan sits with the map questions
- **WHEN** a creator opens the type picker
- **THEN** "Spray area" appears in the map-questions group between the polygon type and
  "Objects on the map", with icon and hint

#### Scenario: Example on hover
- **WHEN** a creator hovers "Spray area"
- **THEN** the example panel shows the paint-mode button with the spray-can icon

#### Scenario: Sub-question restriction unchanged
- **WHEN** the dialog edits a sub-question
- **THEN** "Spray area" is not offered, like the other geo types
