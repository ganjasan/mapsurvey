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

#### Scenario: Only concrete styles get cards; default-ness is a badge
- **WHEN** the creator opens the style picker on any question type that has one
- **THEN** every card names a concrete rendering (choice: "List", "Dropdown with search";
  rating: "Compact scale", "Labeled list", "Stars") and no card is named "Survey default";
  the card matching the survey-wide default carries a corner "Default" ribbon

#### Scenario: Picking the badged card preserves inherit semantics
- **WHEN** the creator selects the ribbon-badged card and saves
- **THEN** the stored `display_style` is `default` (inherit), so a later change of the
  survey-wide style still re-styles the question
