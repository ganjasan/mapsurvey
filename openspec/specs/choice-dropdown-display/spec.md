# choice-dropdown-display Specification

## Purpose

How a `choice` question with `display_style = "dropdown"` renders and behaves for
respondents — a searchable dropdown instead of the radio list — and how the style is
scoped strictly to `choice` questions.

## Requirements

### Requirement: Choice question renders as a searchable dropdown when opted in
When a `choice` question has `display_style = "dropdown"`, the respondent form SHALL
render a search input with a filterable option list instead of the radio list. Typing in
the input SHALL filter options by case-insensitive substring match on the option label in
the respondent's selected language. Choosing an option SHALL display its label in the
input and submit the option's `code` — the same value a radio rendering would submit.
Radio rendering SHALL remain the behavior for `display_style = "default"` and for any
unrecognized stored value.

#### Scenario: Searching narrows the list
- **WHEN** a respondent opens a dropdown-styled choice question with options "Area 1".."Area 35" and types "13"
- **THEN** the visible option list contains "Area 13" and not "Area 1" or "Area 2"

#### Scenario: Selection submits the choice code
- **WHEN** the respondent picks "Area 13" and submits the section
- **THEN** the saved answer references choice code 13, identically to a radio submission

#### Scenario: Existing surveys are unaffected
- **WHEN** a choice question has `display_style = "default"` (or any value other than "dropdown")
- **THEN** it renders as the radio list exactly as before this change

#### Scenario: Required validation still applies
- **WHEN** a required dropdown-styled choice question is submitted with no selection
- **THEN** the form re-renders with the standard required-field error

### Requirement: Dropdown style is scoped to choice questions
The `dropdown` display style SHALL have effect only on `input_type = "choice"`. On any
other question type a stored `display_style = "dropdown"` SHALL be treated as an
unrecognized value and fall back to that type's default rendering.

#### Scenario: Dropdown on a rating question is ignored
- **WHEN** a rating question somehow carries `display_style = "dropdown"`
- **THEN** it renders using the survey's default rating style
