# survey-editor Delta Specification

## ADDED Requirements

### Requirement: Display style picker for choice questions
The question form SHALL offer a display-style selector when the question's input_type is
`choice`, with the options "List" (stored as `default`) and "Dropdown with search"
(stored as `dropdown`). The server SHALL accept `dropdown` only when the question's
input_type is `choice`; for other types the submitted value SHALL be normalized per the
existing display-style validation.

#### Scenario: Creator switches a long choice question to dropdown
- **WHEN** the creator edits a choice question, selects "Dropdown with search", and saves
- **THEN** the question's `display_style` is persisted as `dropdown`

#### Scenario: Picker absent on non-applicable types
- **WHEN** the creator edits a text question
- **THEN** no choice display-style selector is rendered
