## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Survey already exists
**Reason**: Survey names are no longer globally unique. Multiple surveys with the same name are allowed, each identified by UUID.
**Migration**: Import always creates a new survey. Duplicate names are permitted.
