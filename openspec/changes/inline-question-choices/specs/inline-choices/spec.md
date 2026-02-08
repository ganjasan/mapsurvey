## ADDED Requirements

### Requirement: Question stores choices inline as JSONField
The Question model SHALL store answer choices directly in a `choices` JSONField instead of referencing external OptionGroup.

#### Scenario: Question with choices
- **WHEN** a question has input_type choice/multichoice/range/rating
- **THEN** the `choices` field SHALL contain a list of choice objects

#### Scenario: Question without choices
- **WHEN** a question has input_type text/number/point/line/polygon/image/html
- **THEN** the `choices` field SHALL be null or empty list

### Requirement: Choice object structure
Each choice object in `Question.choices` SHALL have a `code` and `name` field with multilingual support.

#### Scenario: Choice with translations
- **WHEN** a choice has translations for multiple languages
- **THEN** the choice object SHALL be structured as:
  ```json
  {"code": 1, "name": {"en": "Never", "ru": "Никогда", "de": "Nie"}}
  ```

#### Scenario: Choice without translations
- **WHEN** a choice has only a default name
- **THEN** the choice object MAY use simple string format:
  ```json
  {"code": 1, "name": "Never"}
  ```

#### Scenario: Choice codes are unique within question
- **WHEN** a question has multiple choices
- **THEN** each choice SHALL have a unique `code` value within that question

### Requirement: Get translated choice name
The Question model SHALL provide a method to retrieve choice name by code and language.

#### Scenario: Get name in specific language
- **WHEN** `question.get_choice_name(code=1, lang="ru")` is called
- **AND** choice with code=1 has Russian translation
- **THEN** method SHALL return the Russian name

#### Scenario: Fallback to English
- **WHEN** `question.get_choice_name(code=1, lang="de")` is called
- **AND** choice with code=1 has no German translation but has English
- **THEN** method SHALL return the English name

#### Scenario: Fallback to first available
- **WHEN** `question.get_choice_name(code=1, lang="de")` is called
- **AND** choice has neither German nor English but has Russian
- **THEN** method SHALL return the Russian name (first available)

#### Scenario: Code not found
- **WHEN** `question.get_choice_name(code=999, lang="en")` is called
- **AND** no choice with code=999 exists
- **THEN** method SHALL return string representation of code ("999")

### Requirement: Answer stores selected choice codes
The Answer model SHALL store selected choices as a list of codes in `selected_choices` JSONField.

#### Scenario: Single choice answer
- **WHEN** user selects one choice with code=2
- **THEN** `answer.selected_choices` SHALL be `[2]`

#### Scenario: Multiple choice answer
- **WHEN** user selects choices with codes 1 and 3
- **THEN** `answer.selected_choices` SHALL be `[1, 3]`

#### Scenario: No choice selected
- **WHEN** user submits form without selecting a choice (optional question)
- **THEN** `answer.selected_choices` SHALL be `[]` or `null`

### Requirement: Get selected choice names from answer
The system SHALL provide a way to retrieve translated names for selected choices.

#### Scenario: Get choice names for answer
- **WHEN** answer has `selected_choices = [1, 3]`
- **AND** calling `get_selected_choice_names(answer, lang="ru")`
- **THEN** system SHALL return list of translated names for codes 1 and 3

### Requirement: Form field generation from inline choices
The form system SHALL generate choice/multichoice fields from `Question.choices` JSONField.

#### Scenario: Generate ChoiceField
- **WHEN** question has input_type="choice"
- **AND** question.choices contains choices
- **THEN** form SHALL render RadioSelect widget with choices from JSONField

#### Scenario: Generate MultipleChoiceField
- **WHEN** question has input_type="multichoice"
- **AND** question.choices contains choices
- **THEN** form SHALL render CheckboxSelectMultiple widget with choices from JSONField

#### Scenario: Generate range field
- **WHEN** question has input_type="range"
- **AND** question.choices contains numeric choices
- **THEN** form SHALL render range slider with min/max derived from choice codes

#### Scenario: Generate rating field
- **WHEN** question has input_type="rating"
- **AND** question.choices contains choices
- **THEN** form SHALL render inline RadioSelect with choices from JSONField

#### Scenario: Translated choice labels
- **WHEN** generating form field with language="ru"
- **THEN** choice labels SHALL use Russian translations from question.choices

### Requirement: Validate choices JSONField structure
The system SHALL validate that `Question.choices` contains valid structure.

#### Scenario: Valid choices structure
- **WHEN** saving question with choices=[{"code": 1, "name": {"en": "Yes"}}]
- **THEN** validation SHALL pass

#### Scenario: Missing code field
- **WHEN** saving question with choices=[{"name": "Yes"}]
- **THEN** validation SHALL fail with error "Each choice must have 'code'"

#### Scenario: Missing name field
- **WHEN** saving question with choices=[{"code": 1}]
- **THEN** validation SHALL fail with error "Each choice must have 'name'"

#### Scenario: Invalid type
- **WHEN** saving question with choices="not a list"
- **THEN** validation SHALL fail with error "choices must be a list"

### Requirement: Admin interface for editing inline choices
The Django admin SHALL provide interface for editing Question.choices.

#### Scenario: Edit choices in admin
- **WHEN** admin edits a question with choices
- **THEN** the choices field SHALL be editable as JSON

#### Scenario: Display choices count
- **WHEN** viewing question list in admin
- **THEN** admin MAY show number of choices for each question
