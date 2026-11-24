## ADDED Requirements

### Requirement: A printed map is framed on the study area
When the survey has a study area, every printed map frame SHALL be centred on the area at the zoom
that fits it (a section's own start position SHALL win only when it lies inside the area), SHALL draw
the area's outline in the frame and SHALL grey the outside when the study area's fog is on. Only the
layers placed on the printed section SHALL be drawn.

#### Scenario: Paper map on the study area
- **GIVEN** a survey whose study area covers 2.4 km² of Midtown, Atlanta, with fog on
- **WHEN** a map section's form is printed
- **THEN** the frame fits the area, its outline is drawn and the outside is greyed

#### Scenario: Only placed layers
- **GIVEN** a layer placed on section 2 only
- **WHEN** section 1 is printed
- **THEN** that layer is not drawn on section 1's frame
