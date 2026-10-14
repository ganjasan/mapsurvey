## MODIFIED Requirements

### Requirement: Question type picker respects the section layout
In a section with `layout = "form"`, the question modal's type picker SHALL show the map types
(`point`, `line`, `polygon`, `spraycan`, and `layer_objects` when it would otherwise be offered)
as DISABLED cards that cannot be picked, with one line under the group naming the reason and the
fix (switch the section's Layout to Map). The server SHALL reject a map `input_type` submitted
into such a section regardless of the picker.

#### Scenario: Map group disabled with a reason in a form section
- **WHEN** the creator opens the new-question modal inside a form-layout section
- **THEN** the "Map questions" group is shown with every card disabled
- **AND** the group says the section has no map and that switching its Layout to Map enables them
- **AND** clicking a disabled card creates nothing

#### Scenario: Map section unchanged
- **WHEN** the creator opens the new-question modal inside a map-layout section
- **THEN** the map cards are enabled and no reason line is shown

#### Scenario: Server-side rejection
- **WHEN** a POST creates a `line` question in a form-layout section
- **THEN** the response is an error and no question is created
