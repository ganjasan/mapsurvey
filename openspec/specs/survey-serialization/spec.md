### Requirement: Export modes
The system SHALL support three export modes: structure, data, and full.

#### Scenario: Structure mode (default)
- **WHEN** user exports with `--mode=structure` or no mode specified
- **THEN** archive contains survey.json + question images only

#### Scenario: Data mode
- **WHEN** user exports with `--mode=data`
- **THEN** archive contains responses.json + user-uploaded files only

#### Scenario: Full mode
- **WHEN** user exports with `--mode=full`
- **THEN** archive contains survey.json + responses.json + all images

### Requirement: Export survey to ZIP via CLI
The system SHALL provide a management command `export_survey` that exports a survey to ZIP archive.

#### Scenario: Export to file
- **WHEN** user runs `python manage.py export_survey <survey_name> --output survey.zip`
- **THEN** system writes ZIP archive to the specified file path

#### Scenario: Export with mode
- **WHEN** user runs `python manage.py export_survey <survey_name> --mode=full`
- **THEN** system exports with the specified mode

#### Scenario: Export to stdout
- **WHEN** user runs `python manage.py export_survey <survey_name>`
- **THEN** system outputs ZIP binary to stdout (for piping)

#### Scenario: Survey not found
- **WHEN** user runs `export_survey` with a non-existent survey name
- **THEN** system exits with error code 1 and message "Survey '<name>' not found"

### Requirement: Export survey to ZIP via Web UI
The system SHALL provide export options in `/editor/` dashboard.

#### Scenario: Export with mode selection
- **WHEN** authenticated user clicks "Export" for a survey
- **THEN** system shows dropdown with options: Structure, Data, Full

#### Scenario: Dropdown visual feedback
- **WHEN** user hovers over export dropdown item
- **THEN** item background SHALL highlight (light gray)
- **WHEN** user clicks/presses dropdown item
- **THEN** item background SHALL change to primary color (blue) with white text

#### Scenario: Download export
- **WHEN** user selects export mode
- **THEN** browser downloads ZIP file named `survey_<name>_<mode>.zip`

#### Scenario: Unauthenticated access
- **WHEN** unauthenticated user accesses export URL directly
- **THEN** system redirects to login page

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

#### Scenario: Question image file inclusion
- **WHEN** a question has an image attached
- **THEN** the image file SHALL be copied to `images/structure/` with filename `<question_code>_<original_name>`

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

#### Scenario: User-uploaded file inclusion
- **WHEN** an answer has uploaded file (image type question)
- **THEN** the file SHALL be copied to `images/uploads/` with filename `<session_id>_<question_code>_<original_name>`

#### Scenario: Export survey without sections
- **WHEN** a survey has no sections defined
- **THEN** system SHALL export valid archive with empty `sections` array

### Requirement: Responses serialization format
The responses.json SHALL contain all survey sessions and answers.

#### Scenario: Session serialization
- **WHEN** data or full mode is exported
- **THEN** each session SHALL include:
  - `start_datetime`: ISO 8601 timestamp
  - `end_datetime`: ISO 8601 timestamp or null
  - `answers`: array of answers for this session

#### Scenario: Answer serialization
- **WHEN** an answer is exported
- **THEN** it SHALL include:
  - `question_code`: reference to question by code
  - `numeric`, `text`, `yn`: scalar values (if present)
  - `point`, `line`, `polygon`: WKT strings (if present)
  - `choices`: array of choice names resolved from codes (for choice/multichoice)
  - `sub_answers`: nested array for hierarchical answers

#### Scenario: Answer with geo data
- **WHEN** an answer has point/line/polygon data
- **THEN** the geo field SHALL be serialized as WKT string

#### Scenario: Export survey without responses
- **WHEN** data mode is exported for survey with no sessions
- **THEN** system SHALL export valid archive with empty `sessions` array

### Requirement: Import survey from ZIP via CLI
The system SHALL provide a management command `import_survey` that creates a survey from ZIP archive.

#### Scenario: Import from file
- **WHEN** user runs `python manage.py import_survey survey.zip`
- **THEN** system creates all survey objects and outputs "Survey '<name>' imported successfully"

#### Scenario: Import from stdin
- **WHEN** user pipes ZIP to `python manage.py import_survey -`
- **THEN** system reads ZIP from stdin and imports the survey

#### Scenario: File not found
- **WHEN** user runs `import_survey` with a path to non-existent file
- **THEN** system exits with error code 1 and message "File '<path>' not found"

#### Scenario: Duplicate survey name allowed
- **WHEN** user imports a survey with a name that already exists in the database
- **THEN** system SHALL create the survey successfully with a new UUID

#### Scenario: Invalid archive format
- **WHEN** user attempts to import invalid ZIP or missing survey.json
- **THEN** system exits with error code 1 and descriptive validation error message

#### Scenario: Unsupported format version
- **WHEN** user attempts to import archive with unsupported version (e.g., "2.0")
- **THEN** system exits with error code 1 and message "Unsupported format version '<version>'. Supported: 1.0"

#### Scenario: Invalid input_type in question
- **WHEN** JSON contains a question with input_type not in allowed choices
- **THEN** system exits with error code 1 and message "Invalid input_type '<type>' for question '<code>'"

#### Scenario: Missing choices for choice-based input types
- **WHEN** JSON contains a question with input_type choice/multichoice/range/rating without `choices` array
- **AND** no legacy `option_group_name` is present
- **THEN** system exits with error code 1 and message "Question '<code>': input_type '<type>' requires choices"

### Requirement: Import survey from ZIP via Web UI
The system SHALL provide an upload form in `/editor/` dashboard to import surveys.

#### Scenario: Import from editor
- **WHEN** authenticated user clicks "Import Survey" and uploads ZIP file
- **THEN** system imports survey and redirects to `/editor/` with success message

#### Scenario: Import validation error in Web UI
- **WHEN** user uploads invalid archive via Web UI
- **THEN** system shows error message on same page without redirect

#### Scenario: Unauthenticated upload
- **WHEN** unauthenticated user accesses import URL directly
- **THEN** system redirects to login page

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

### Requirement: Import responses from archive
The import SHALL restore survey sessions and answers when present in archive.

#### Scenario: Import full archive
- **WHEN** archive contains both survey.json and responses.json
- **THEN** system SHALL create structure first, then import all sessions and answers

#### Scenario: Import data-only archive
- **WHEN** archive contains only responses.json (data mode export)
- **THEN** system SHALL require survey to already exist and match by name

#### Scenario: Answer references missing question
- **WHEN** responses.json contains answer with question_code not in survey
- **THEN** system SHALL skip answer and output warning "Answer references unknown question '<code>', skipped"

#### Scenario: Answer choice name not found
- **WHEN** answer contains choice name not in Question.choices
- **THEN** system SHALL skip that choice and output warning "Choice '<name>' not found for question '<code>', skipped"

#### Scenario: Import geo answer
- **WHEN** responses.json contains answer with WKT geo data
- **THEN** system SHALL parse WKT and create valid geo field value

### Requirement: Handle geo fields in sections
The serialization SHALL properly handle GeoDjango PointField for section map positions.

#### Scenario: Export geo point
- **WHEN** a section with start_map_position is exported
- **THEN** the point SHALL be serialized as WKT string (e.g., "POINT(30.317 59.945)")

#### Scenario: Import geo point
- **WHEN** archive contains WKT point string
- **THEN** the system SHALL parse WKT and create valid PointField value

#### Scenario: Invalid WKT string
- **WHEN** archive contains invalid WKT string for start_map_position
- **THEN** system exits with error code 1 and message "Invalid WKT for section '<name>': <parse_error>"

### Requirement: Handle field length limits during import
The import SHALL truncate field values that exceed database column limits.

#### Scenario: Section code exceeds max length
- **WHEN** archive contains section with code longer than 8 characters
- **THEN** system SHALL truncate code to 8 characters

#### Scenario: Section name exceeds max length
- **WHEN** archive contains section with name longer than 45 characters
- **THEN** system SHALL truncate name to 45 characters

#### Scenario: Survey name exceeds max length
- **WHEN** archive contains survey with name longer than 45 characters
- **THEN** system SHALL truncate name to 45 characters

### Requirement: Handle image files during import
The import SHALL extract image files and link them to questions/answers.

#### Scenario: Extract structure image file
- **WHEN** archive contains image in `images/structure/` matching question's image field
- **THEN** system SHALL extract file to MEDIA_ROOT/images/ and set question.image field

#### Scenario: Extract uploaded image file
- **WHEN** archive contains file in `images/uploads/` for an answer
- **THEN** system SHALL extract file to MEDIA_ROOT/uploads/ and link to answer

#### Scenario: Missing structure image in archive
- **WHEN** survey.json references image but file is missing in `images/structure/`
- **THEN** system SHALL set image field to null and output warning "Image '<filename>' not found in archive for question '<code>'"

#### Scenario: Missing uploaded file in archive
- **WHEN** responses.json references file but it's missing in `images/uploads/`
- **THEN** system SHALL set field to null and output warning "Upload '<filename>' not found in archive for answer"
