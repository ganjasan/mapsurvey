# Answer Prepopulation Specification

## Purpose
How a respondent's existing answers are loaded back into a section's form when they navigate to it again, across every field type including geo features and their sub-questions, so that going back never silently discards work.
## Requirements
### Requirement: Load existing answers on section visit
When a user navigates to a survey section via GET request and a survey session exists, the system SHALL query all Answer records for the current session and section, and pass them as initial values to the form.

#### Scenario: User navigates back to a previously completed section
- **WHEN** user clicks the "Back" button to return to a section they already submitted
- **THEN** the form fields SHALL display the previously saved answers for that section

#### Scenario: User visits a section for the first time
- **WHEN** user visits a section that has no saved answers for the current session
- **THEN** the form fields SHALL render empty (default behavior)

#### Scenario: No active survey session
- **WHEN** user visits a section URL without an active survey session
- **THEN** the system SHALL behave as before (redirect or create session), with no prepopulation attempted

### Requirement: Prepopulate text and number fields
The system SHALL set the initial value of text, text_line, and number form fields from the corresponding Answer record's `text` or `numeric` field.

#### Scenario: Text field with saved answer
- **WHEN** a section is loaded and a text/text_line question has a saved Answer with `text` value
- **THEN** the text input SHALL display the saved text value

#### Scenario: Number field with saved answer
- **WHEN** a section is loaded and a number question has a saved Answer with `numeric` value
- **THEN** the number input SHALL display the saved numeric value

### Requirement: Prepopulate choice and multichoice fields
The system SHALL pre-select the saved choice codes from `Answer.selected_choices` for choice and multichoice questions. When the saved selection includes the question's write-in option, the write-in input SHALL be prefilled with `Answer.text` and rendered visible.

#### Scenario: Single choice field with saved answer
- **WHEN** a section is loaded and a choice question has a saved Answer with `selected_choices` containing one code
- **THEN** the corresponding radio button SHALL be checked

#### Scenario: Multichoice field with saved answer
- **WHEN** a section is loaded and a multichoice question has a saved Answer with `selected_choices` containing multiple codes
- **THEN** all corresponding checkboxes SHALL be checked

#### Scenario: Write-in text restored
- **WHEN** a section is loaded and a choice question's saved Answer selected the write-in option with `text="wet towel"`
- **THEN** the write-in input under that option SHALL be visible, enabled and hold "wet towel"

### Requirement: Prepopulate range and rating fields
The system SHALL set the initial value of range and rating fields from the saved Answer's `numeric` field.

#### Scenario: Range field with saved answer
- **WHEN** a section is loaded and a range question has a saved Answer with `numeric` value
- **THEN** the range slider SHALL display the saved numeric value

#### Scenario: Rating field with saved answer
- **WHEN** a section is loaded and a rating question has a saved Answer with `numeric` value
- **THEN** the rating input SHALL display the saved numeric value

### Requirement: Prepopulate datetime fields
The system SHALL set the initial value of datetime fields from the saved Answer's `text` field.

#### Scenario: Datetime field with saved answer
- **WHEN** a section is loaded and a datetime question has a saved Answer with `text` value
- **THEN** the datetime input SHALL display the saved datetime value

### Requirement: Restore geo features on map
The system SHALL restore previously saved geo answers (point, line, polygon) as drawn features on the Leaflet map when a section is loaded. Each Answer's geometry SHALL be converted to GeoJSON and rendered as an editable layer on the map.

#### Scenario: Point features restored
- **WHEN** a section is loaded and a point question has saved Answer records with `point` geometry
- **THEN** the map SHALL display markers at the saved point locations, each associated with its question code

#### Scenario: Line features restored
- **WHEN** a section is loaded and a line question has saved Answer records with `line` geometry
- **THEN** the map SHALL display polylines at the saved line geometries

#### Scenario: Polygon features restored
- **WHEN** a section is loaded and a polygon question has saved Answer records with `polygon` geometry
- **THEN** the map SHALL display polygons at the saved polygon geometries

#### Scenario: Multiple geo answers for one question
- **WHEN** a question has multiple saved geo Answer records (e.g., several points)
- **THEN** all saved features SHALL be restored on the map

### Requirement: Restore sub-question values for geo features
When geo features are restored on the map, the system SHALL also restore sub-question answer values as properties of each GeoJSON feature, so that popups display previously entered sub-question data. The restored value SHALL be chosen by the sub-question's input type, not by which Answer columns happen to be set; a choice sub-answer that selected the write-in option SHALL additionally restore its text under the `<code>-other` property.

#### Scenario: Geo feature with sub-question answers
- **WHEN** a geo Answer has child Answer records (via `parent_answer_id`) for sub-questions
- **THEN** the restored map feature SHALL include sub-question values in its `properties`, matching the format used during initial submission

#### Scenario: Geo feature without sub-questions
- **WHEN** a geo Answer has no child Answer records
- **THEN** the feature SHALL be restored with only the `question_id` property

#### Scenario: Choice sub-answer with write-in text
- **WHEN** a child Answer of a choice sub-question S1 has `selected_choices=[4]` and `text="graffiti"`
- **THEN** the feature's properties SHALL carry `S1: ["4"]` and `S1-other: ["graffiti"]`, never `S1: ["graffiti"]`

### Requirement: Update existing answers on re-submission
When a user re-submits a section that already has saved answers, the system SHALL delete the existing Answer records for that session and section before saving new ones, to prevent duplicate answers.

#### Scenario: Re-submitting a previously completed section
- **WHEN** user modifies answers on a previously completed section and submits
- **THEN** the old Answer records for that session and section SHALL be removed and new records saved

#### Scenario: Re-submitting does not affect other sections
- **WHEN** user re-submits a section
- **THEN** Answer records for other sections in the same session SHALL NOT be affected

### Requirement: Prepopulate sub-question forms
The system SHALL pass existing sub-question answer data as initial values to sub-question forms rendered in geo feature popups.

#### Scenario: Sub-question form with saved text answer
- **WHEN** a geo feature popup is opened and a text sub-question has a saved child Answer
- **THEN** the sub-question text field SHALL display the saved value

#### Scenario: Sub-question form with saved choice answer
- **WHEN** a geo feature popup is opened and a choice sub-question has a saved child Answer
- **THEN** the sub-question choice field SHALL have the saved option pre-selected

