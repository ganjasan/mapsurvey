## ADDED Requirements

### Requirement: A printed map uses its section's effective area
A printed section map SHALL be framed on, and draw, its section's effective study area: its own area,
the survey's area, or none. A section on No area SHALL print as it would without a study area. A
change of any section's choice or own area SHALL produce a new form.

#### Scenario: Own area on paper
- **WHEN** a form is printed for a survey whose second section has an own corridor area
- **THEN** the second section's map is framed on the corridor and draws its outline, and the first section's map is framed on the survey's area

#### Scenario: No area on paper
- **WHEN** a section on No area is printed
- **THEN** its map is framed on its start position and draws no outline
