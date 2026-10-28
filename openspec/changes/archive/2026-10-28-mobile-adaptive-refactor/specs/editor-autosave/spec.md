# editor-autosave

## ADDED Requirements

### Requirement: Question edits save automatically
Changes to question fields in the editor SHALL be persisted automatically after input
settles (debounced), on all viewports, using the same server-side save path as the former
explicit save action.

#### Scenario: Edit persists without pressing save
- **WHEN** the creator changes a question's text and stops typing
- **THEN** the change is persisted within a few seconds without any explicit save action

#### Scenario: Rapid typing does not spam the server
- **WHEN** the creator types continuously in a field
- **THEN** save requests are debounced so at most one request is in flight per settle period

### Requirement: Saved-state indicator
The editor SHALL display a persistent indicator reflecting save state: saved, saving, or
error. A failed autosave SHALL be visibly reported with a retry affordance and MUST NOT
fail silently.

#### Scenario: Indicator confirms save
- **WHEN** an autosave completes successfully
- **THEN** the indicator shows an "all changes saved" state

#### Scenario: Failure is loud
- **WHEN** an autosave request fails (network or server error)
- **THEN** the indicator shows an error state with a retry affordance and the edited content is not lost from the form

### Requirement: Explicit save button is removed from edit forms
Question EDIT forms SHALL NOT render explicit Save/Apply buttons on any viewport once
autosave is enabled; the saved-state indicator takes their place. New-question forms keep
an explicit Create action — a question record must not be manufactured before the creator
commits to one.

#### Scenario: No save button on desktop edit form
- **WHEN** the creator opens an existing question's form at 1280px width with autosave enabled
- **THEN** no Save or Apply button is rendered and the saved-state indicator is present

#### Scenario: New-question form keeps Create
- **WHEN** the creator opens the new-question form with autosave enabled
- **THEN** an explicit Create button is rendered and no autosave fires before it is pressed
