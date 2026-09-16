## MODIFIED Requirements

### Requirement: Choices editor for choice-based questions
The system SHALL display a dynamic choices editor when the question's input_type is choice, multichoice, range, or rating. The editor SHALL allow adding and removing choice rows. Each row SHALL have a code (integer) and name fields (one per available language for multilingual surveys, or a single field for single-language surveys). On save, choices SHALL be serialized to the `Question.choices` JSONField format: `[{"code": N, "name": {"en": "...", "ru": "..."}}]`. For choice and multichoice questions each row SHALL also offer an "Other" checkbox that marks the row as the write-in option; checking one row SHALL uncheck any other, the checked row SHALL serialize with `"other": true`, the column SHALL not be offered for range and rating questions, and the server SHALL keep at most one flag per question. The choices editor script SHALL initialise for a star-rating question with no stored choices without error.

#### Scenario: Add choices to a new choice question
- **WHEN** the user creates a question with input_type "choice", adds two choices with codes 1 ("Yes") and 2 ("No"), and saves
- **THEN** the Question.choices field is set to `[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]`

#### Scenario: Multilingual choices
- **WHEN** the survey has available_languages ["en", "ru"] and the user adds a choice with code 1, en name "Yes", ru name "Да"
- **THEN** the choice is stored as `{"code": 1, "name": {"en": "Yes", "ru": "Да"}}`

#### Scenario: Remove a choice
- **WHEN** the user removes the second choice from a question with 3 choices
- **THEN** the choices JSONField is updated to contain only the remaining 2 choices

#### Scenario: Choices editor hidden for non-choice types
- **WHEN** the user selects input_type "text" or "point"
- **THEN** the choices editor is not displayed

#### Scenario: Mark the write-in option
- **WHEN** the user checks "Other" on the row with code 4 and saves
- **THEN** that choice is stored as `{"code": 4, "name": "Other (specify)", "other": true}` and the other rows carry no flag

#### Scenario: Only one row can be the write-in option
- **WHEN** the user checks "Other" on code 2 while code 4 is checked
- **THEN** code 4 is unchecked, and a save carrying both flags anyway stores the flag on the first one only

#### Scenario: Reopening keeps the flag
- **WHEN** the user reopens the modal of a question whose code 4 carries `other: true`
- **THEN** the "Other" checkbox on that row is checked

#### Scenario: Star-rating modal initialises
- **WHEN** the modal opens for a rating question with display style "stars" and no stored choices
- **THEN** five star rows are added and the script completes without a ReferenceError
