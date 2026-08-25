# choice-dropdown-display Delta Specification

## ADDED Requirements

### Requirement: An untouched dropdown holds no value
A `choice` question rendered with `display_style = "dropdown"` SHALL render a blank
placeholder option, selected whenever the question has no stored answer, so the browser
cannot auto-select the first real choice. An untouched dropdown SHALL therefore submit
no value, SHALL be treated as unanswered by the respondent form's required check, and
SHALL store no answer. The placeholder SHALL NOT appear in the visible option list.

#### Scenario: Nothing chosen means nothing stored
- **WHEN** a section holding a non-required dropdown question is submitted without touching it
- **THEN** no answer is stored for that question

#### Scenario: Required dropdown blocks the forward button
- **WHEN** the respondent submits a section whose required dropdown question was never touched
- **THEN** the section is not submitted and the question is marked as missing, exactly as an unanswered radio question is

#### Scenario: Stored answer selects its own option
- **WHEN** a dropdown question with a stored answer is rendered
- **THEN** that option is selected, the placeholder is not, and the search input shows the option's label

#### Scenario: Placeholder stays out of the visible list
- **WHEN** the respondent opens the dropdown and clears the search box
- **THEN** the list shows only real options
