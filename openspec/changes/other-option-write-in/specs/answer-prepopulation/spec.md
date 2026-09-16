## MODIFIED Requirements

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
