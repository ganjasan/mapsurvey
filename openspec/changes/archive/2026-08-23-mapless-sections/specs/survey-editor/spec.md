# survey-editor Delta Specification

## ADDED Requirements

### Requirement: Section layout setting
The section settings form SHALL offer the layout choice — "Map" (default) and "Form" —
persisted to `SurveySection.layout`. When "Form" is selected, the map-position fields
(start position, zoom, geolocation) SHALL be hidden in the form; their stored values are
preserved for a later switch back. Saving `layout = "form"` on a section that contains geo
questions SHALL be refused with a message naming those questions.

#### Scenario: Creator makes a welcome section
- **WHEN** the creator sets the head section's layout to "Form" and saves
- **THEN** the section persists `layout = "form"` and respondent preview renders it full-width

#### Scenario: Switch refused over geo questions
- **WHEN** the creator sets layout "Form" on a section with a point question and saves
- **THEN** the form re-renders with an error naming the point question and the section stays `layout = "map"`

### Requirement: Question type picker respects the section layout
In a section with `layout = "form"`, the question modal's type picker SHALL NOT offer the
geo group (`point`, `line`, `polygon`), and the server SHALL reject a geo `input_type`
submitted into such a section regardless of the picker.

#### Scenario: Geo group absent in a form section
- **WHEN** the creator opens the new-question modal inside a form-layout section
- **THEN** the "Map questions" group is not shown

#### Scenario: Server-side rejection
- **WHEN** a POST creates a `line` question in a form-layout section
- **THEN** the response is an error and no question is created
