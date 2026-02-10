## MODIFIED Requirements

### Requirement: ZIP archive structure
The exported ZIP SHALL contain survey definition JSON and media files.

#### Scenario: Archive contents
- **WHEN** a survey is exported
- **THEN** the ZIP SHALL contain (based on mode):
  - `survey.json`: survey definition (modes: structure, full)
  - `responses.json`: sessions and answers (modes: data, full)
  - `images/structure/`: question images (modes: structure, full)
  - `images/uploads/`: user-uploaded answer files (modes: data, full)

#### Scenario: JSON format structure
- **WHEN** a survey is exported
- **THEN** `survey.json` SHALL include:
  - `version`: format version string (e.g., "1.0")
  - `exported_at`: ISO 8601 timestamp
  - `survey`: object containing survey header fields and nested sections

#### Scenario: Section serialization
- **WHEN** a survey with multiple sections is exported
- **THEN** each section SHALL include:
  - All SurveySection fields (name, title, subheading, code, is_head, start_map_position, start_map_zoom)
  - `next_section_name`: name of next section or null
  - `prev_section_name`: name of previous section or null
  - `questions`: array of questions in order

#### Scenario: Question serialization with hierarchy
- **WHEN** a survey with parent-child questions is exported
- **THEN** child questions SHALL be nested under parent in a `sub_questions` array

#### Scenario: Question serialization with inline choices
- **WHEN** a question has input_type choice/multichoice/range/rating
- **THEN** the question object SHALL include `choices` array with inline choice objects:
  ```json
  {
    "code": "Q001",
    "input_type": "choice",
    "choices": [
      {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
      {"code": 2, "name": {"en": "No", "ru": "Нет"}}
    ]
  }
  ```

#### Scenario: Question image file inclusion
- **WHEN** a question has an image attached
- **THEN** the image file SHALL be copied to `images/structure/` with filename `<question_code>_<original_name>`

#### Scenario: User-uploaded file inclusion
- **WHEN** an answer has uploaded file (image type question)
- **THEN** the file SHALL be copied to `images/uploads/` with filename `<session_id>_<question_code>_<original_name>`

#### Scenario: Export survey without sections
- **WHEN** a survey has no sections defined
- **THEN** system SHALL export valid archive with empty `sections` array

### Requirement: Import creates related objects correctly
The import command SHALL create all related objects in the correct order to satisfy foreign key constraints.

#### Scenario: Import order
- **WHEN** a survey archive is imported
- **THEN** objects SHALL be created in this order:
  1. Organization (if specified and doesn't exist)
  2. SurveyHeader
  3. SurveySections (without next/prev links)
  4. Questions (parents before children) with choices and image extraction
  5. SurveySection next/prev links resolved

#### Scenario: Atomic import transaction
- **WHEN** import fails at any step
- **THEN** all created objects SHALL be rolled back and database remains unchanged

#### Scenario: Reuse existing Organization
- **WHEN** archive specifies an organization name that already exists in database
- **THEN** system SHALL use the existing Organization instead of creating duplicate

#### Scenario: Generate unique question codes with remapping
- **WHEN** archive contains a question with code that already exists in database
- **THEN** system SHALL generate a new unique code and store mapping old_code → new_code

#### Scenario: Apply code remapping to responses
- **WHEN** importing responses.json after question codes were remapped
- **THEN** system SHALL translate answer.question_code using the remapping table

#### Scenario: Apply code remapping to parent references
- **WHEN** question has parent_question reference and parent code was remapped
- **THEN** system SHALL resolve parent using remapped code

#### Scenario: Broken section link warning
- **WHEN** archive contains a section with next_section_name referencing non-existent section
- **THEN** system SHALL set the link to null and output warning "Section '<name>': next_section '<ref>' not found, set to null"

### Requirement: Import question with inline choices
The import SHALL parse inline choices from question object instead of referencing OptionGroups.

#### Scenario: Import question with choices
- **WHEN** archive contains question with `choices` array
- **THEN** system SHALL store choices in `Question.choices` JSONField

#### Scenario: Import legacy format with option_groups
- **WHEN** archive contains legacy `option_groups` array and questions with `option_group_name`
- **THEN** system SHALL convert to inline format:
  1. Find referenced OptionGroup in `option_groups` array
  2. Convert choices to inline format with translations
  3. Store in `Question.choices`

#### Scenario: Missing choices for choice-based input types
- **WHEN** JSON contains question with input_type choice/multichoice/range/rating without `choices` array
- **AND** no legacy `option_group_name` is present
- **THEN** system exits with error code 1 and message "Question '<code>': input_type '<type>' requires choices"

### Requirement: Answer serialization with choice codes
The answer serialization SHALL use choice names (not codes) for readability.

#### Scenario: Answer serialization
- **WHEN** an answer is exported
- **THEN** it SHALL include:
  - `question_code`: reference to question by code
  - `numeric`, `text`, `yn`: scalar values (if present)
  - `point`, `line`, `polygon`: WKT strings (if present)
  - `choices`: array of choice names (resolved from codes)
  - `sub_answers`: nested array for hierarchical answers

#### Scenario: Answer with geo data
- **WHEN** an answer has point/line/polygon data
- **THEN** the geo field SHALL be serialized as WKT string

#### Scenario: Export survey without responses
- **WHEN** data mode is exported for survey with no sessions
- **THEN** system SHALL export valid archive with empty `sessions` array

### Requirement: Import answer choices by name
The import SHALL convert choice names back to codes when restoring answers.

#### Scenario: Import answer with choices
- **WHEN** responses.json contains answer with `choices: ["Yes", "Maybe"]`
- **THEN** system SHALL:
  1. Look up each name in `Question.choices` by matching name values
  2. Store corresponding codes in `Answer.selected_choices`

#### Scenario: Answer choice name not found
- **WHEN** answer contains choice name not in Question.choices
- **THEN** system SHALL skip that choice and output warning "Choice '<name>' not found for question '<code>', skipped"

## REMOVED Requirements

### Requirement: OptionGroup deduplication
**Reason**: OptionGroups are removed; choices are now stored inline in each question.
**Migration**: Choices are automatically converted to inline format during data migration.

### Requirement: Reuse existing OptionGroup
**Reason**: OptionGroups are removed; each question has its own independent choices.
**Migration**: N/A - no shared OptionGroups after migration.

### Requirement: Add translations to existing OptionChoices
**Reason**: OptionChoiceTranslation model is removed; translations are inline in choices JSON.
**Migration**: Translations are embedded in the `name` field of each choice object.
