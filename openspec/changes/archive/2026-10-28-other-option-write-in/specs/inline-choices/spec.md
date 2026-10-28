## MODIFIED Requirements

### Requirement: Choice object structure
Each choice object in `Question.choices` SHALL have a `code` and `name` field with multilingual support. A choice object of a `choice` or `multichoice` question MAY additionally carry `"other": true` to mark it as the question's write-in option; at most one choice per question SHALL carry the flag.

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

#### Scenario: Write-in option
- **WHEN** a choice is the question's write-in option
- **THEN** the choice object SHALL be structured as:
  ```json
  {"code": 4, "name": "Other (specify)", "other": true}
  ```
  and the validator SHALL accept it

### Requirement: Answer stores selected choice codes
The Answer model SHALL store selected choices as a list of codes in `selected_choices` JSONField. When the selection includes the question's write-in option, the same Answer row SHALL hold the respondent's write-in text in `text`.

#### Scenario: Single choice answer
- **WHEN** user selects one choice with code=2
- **THEN** `answer.selected_choices` SHALL be `[2]`

#### Scenario: Multiple choice answer
- **WHEN** user selects choices with codes 1 and 3
- **THEN** `answer.selected_choices` SHALL be `[1, 3]`

#### Scenario: No choice selected
- **WHEN** user submits form without selecting a choice (optional question)
- **THEN** `answer.selected_choices` SHALL be `[]` or `null`

#### Scenario: Write-in option selected
- **WHEN** user selects the write-in option with code=4 and types "wet towel"
- **THEN** `answer.selected_choices` SHALL be `[4]` and `answer.text` SHALL be `"wet towel"`
