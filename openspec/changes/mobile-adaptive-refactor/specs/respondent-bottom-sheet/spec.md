# respondent-bottom-sheet

## ADDED Requirements

### Requirement: Question panel is a bottom sheet on mobile
On viewports narrower than 768px the respondent survey page SHALL render the question
panel as a bottom sheet over an always-visible map. The sheet SHALL support at least a
collapsed (title and progress visible) and an expanded state, switchable by dragging its
handle or tapping it. The map SHALL remain pannable and zoomable while the sheet is shown.

#### Scenario: Map visible on first load
- **WHEN** a respondent opens a survey section with a geo question at 390px width
- **THEN** the map occupies the viewport with the question sheet over its lower portion, and the map can be panned

#### Scenario: Sheet collapses for map work
- **WHEN** the respondent drags the sheet handle down
- **THEN** the sheet collapses to title and progress, leaving the map fully visible

#### Scenario: Desktop unchanged
- **WHEN** the survey page is opened at 1280px width
- **THEN** the pre-change panel layout is rendered

### Requirement: Applied geometry is confirmed in the panel
The sheet SHALL visibly confirm each applied geometry (point, line or area): after apply,
the corresponding question SHALL show the count of placed geometries and SHALL provide an
affordance to edit or delete them.

#### Scenario: Pin count after apply
- **WHEN** the respondent applies a point via the crosshair flow
- **THEN** the question card in the sheet shows one geometry recorded (e.g. "1 place added") instead of its initial untouched state

### Requirement: Instruction copy matches the touch interaction
Geo question instructions on touch devices SHALL describe the actual interaction (activate
the question, position via crosshair, apply) and SHALL NOT instruct the respondent to tap
the map when tapping the map has no effect.

#### Scenario: Point instruction on touch
- **WHEN** a point question is rendered on a touch device
- **THEN** its instruction text tells the respondent to tap the question card and position the pin, not to "click the map"

### Requirement: Bottom sheet is gated by a kill switch
The bottom-sheet layout SHALL be enabled only when the corresponding environment flag is
set; when unset, the pre-change respondent layout is served.

#### Scenario: Flag off serves legacy panel
- **WHEN** the flag is unset and a survey section is opened at 390px width
- **THEN** the pre-change panel layout is rendered
