# Survey Language Selection

This spec defines how respondents select their preferred language when starting a multilingual survey.

## ADDED Requirements

### Requirement: Language selection screen is the first screen for multilingual surveys
The system SHALL display a language selection screen as the first step when a respondent opens a multilingual survey.

#### Scenario: Multilingual survey entry
- **WHEN** a respondent navigates to a survey that has multiple languages configured
- **THEN** the system MUST redirect to the language selection screen before showing any survey content

#### Scenario: Single-language survey entry
- **WHEN** a respondent navigates to a survey that has no languages configured (single-language)
- **THEN** the system MUST skip the language selection screen and go directly to the first section

### Requirement: Language selection screen displays all available languages
The system SHALL display all languages configured for the survey on the language selection screen.

#### Scenario: Language list display
- **WHEN** the language selection screen is shown
- **THEN** all languages from the survey's language list MUST be displayed as selectable options

#### Scenario: Language display format
- **WHEN** languages are displayed on the selection screen
- **THEN** each language MUST be shown with its native name (e.g., "English", "Русский", "Deutsch")

### Requirement: Respondent can select a language
The system SHALL allow the respondent to select one language from the available options.

#### Scenario: Language selection
- **WHEN** a respondent clicks on a language option
- **THEN** the system MUST record the selected language and proceed to the first survey section

### Requirement: Selected language is stored in survey session
The system SHALL store the selected language in the survey session for the duration of the survey.

#### Scenario: Language stored in session
- **WHEN** a respondent selects a language
- **THEN** the selected language code MUST be stored in the SurveySession record

#### Scenario: Language persists across sections
- **WHEN** a respondent navigates between survey sections
- **THEN** the selected language MUST remain active throughout the entire survey

### Requirement: Survey content is displayed in selected language
The system SHALL use the selected language to retrieve and display translated survey content.

#### Scenario: Section content in selected language
- **WHEN** a respondent views a survey section
- **THEN** the section title and subheading MUST be displayed in the selected language (or original if no translation)

#### Scenario: Question content in selected language
- **WHEN** a respondent views a question
- **THEN** the question name and subtext MUST be displayed in the selected language (or original if no translation)

#### Scenario: Option choices in selected language
- **WHEN** a respondent views a choice/multichoice question
- **THEN** the option choice names MUST be displayed in the selected language (or original if no translation)

### Requirement: Language selection has a dedicated URL
The system SHALL provide a dedicated URL endpoint for the language selection screen.

#### Scenario: Language selection URL pattern
- **WHEN** the language selection screen is accessed
- **THEN** the URL MUST follow the pattern `/surveys/<survey_name>/language/`

### Requirement: Direct section access redirects to language selection
The system SHALL redirect to the language selection screen if a respondent tries to access a section directly without having selected a language.

#### Scenario: Direct section access without language
- **WHEN** a respondent navigates directly to a survey section URL for a multilingual survey
- **AND** no language has been selected in the session
- **THEN** the system MUST redirect to the language selection screen
