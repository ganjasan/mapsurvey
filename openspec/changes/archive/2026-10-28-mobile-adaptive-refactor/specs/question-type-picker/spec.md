# question-type-picker (delta)

## ADDED Requirements

### Requirement: Full-screen picker on mobile
On viewports narrower than 768px the question type picker SHALL be presented full-screen
instead of as a floating dialog. The map input types (point, line, area) SHALL be rendered
as their own visually distinct group. Selecting a type SHALL reveal the question's editing
form directly, with no intermediate confirmation step; the question record is created on
first save. Desktop dialog behavior SHALL remain unchanged.

#### Scenario: Picker fills the screen on mobile
- **WHEN** a creator taps "add question" in a section at 390px width
- **THEN** the question dialog (type picker + form) occupies the full viewport with map types grouped separately

#### Scenario: Type selection opens the editing form
- **WHEN** the creator taps the Point type in the mobile picker
- **THEN** the point question's editing fields are shown in the same view without an intermediate step

#### Scenario: Desktop dialog unchanged
- **WHEN** a creator adds a question at 1280px width
- **THEN** the pre-change picker dialog is shown
