# Survey Serialization (Delta)

This delta spec extends the existing survey-serialization capability to support multilingual content.

## ADDED Requirements

### Requirement: Export available languages
The system SHALL include `available_languages` field in survey.json when exporting a survey.

#### Scenario: Survey with languages configured
- **WHEN** a survey with `available_languages = ["en", "ru", "de"]` is exported
- **THEN** survey.json SHALL include `"available_languages": ["en", "ru", "de"]`

#### Scenario: Survey without languages configured
- **WHEN** a survey with no languages configured is exported
- **THEN** survey.json SHALL include `"available_languages": []` or omit the field

### Requirement: Export section translations
The system SHALL include translations for each section in survey.json.

#### Scenario: Section with translations
- **WHEN** a section has translations for multiple languages
- **THEN** survey.json section object SHALL include `"translations"` array with objects containing:
  - `language`: ISO 639-1 code
  - `title`: translated title (or null)
  - `subheading`: translated subheading (or null)

#### Scenario: Section without translations
- **WHEN** a section has no translations
- **THEN** survey.json section object SHALL include `"translations": []`

### Requirement: Export question translations
The system SHALL include translations for each question in survey.json.

#### Scenario: Question with translations
- **WHEN** a question has translations for multiple languages
- **THEN** survey.json question object SHALL include `"translations"` array with objects containing:
  - `language`: ISO 639-1 code
  - `name`: translated name (or null)
  - `subtext`: translated subtext (or null)

#### Scenario: Question without translations
- **WHEN** a question has no translations
- **THEN** survey.json question object SHALL include `"translations": []`

### Requirement: Export option choice translations
The system SHALL include translations for each option choice in survey.json.

#### Scenario: Option choice with translations
- **WHEN** an option choice has translations for multiple languages
- **THEN** survey.json option choice object SHALL include `"translations"` array with objects containing:
  - `language`: ISO 639-1 code
  - `name`: translated name

#### Scenario: Option choice without translations
- **WHEN** an option choice has no translations
- **THEN** survey.json option choice object SHALL include `"translations": []`

### Requirement: Import available languages
The system SHALL restore `available_languages` field when importing a survey.

#### Scenario: Import survey with languages
- **WHEN** survey.json contains `"available_languages": ["en", "ru"]`
- **THEN** imported SurveyHeader SHALL have `available_languages = ["en", "ru"]`

#### Scenario: Import survey without languages field
- **WHEN** survey.json does not contain `available_languages` field
- **THEN** imported SurveyHeader SHALL have `available_languages = []`

### Requirement: Import section translations
The system SHALL create SurveySectionTranslation records when importing a survey.

#### Scenario: Import section with translations
- **WHEN** survey.json section contains translations array
- **THEN** system SHALL create SurveySectionTranslation record for each translation

#### Scenario: Import section without translations
- **WHEN** survey.json section has empty translations array
- **THEN** system SHALL not create any SurveySectionTranslation records for that section

### Requirement: Import question translations
The system SHALL create QuestionTranslation records when importing a survey.

#### Scenario: Import question with translations
- **WHEN** survey.json question contains translations array
- **THEN** system SHALL create QuestionTranslation record for each translation

#### Scenario: Import question without translations
- **WHEN** survey.json question has empty translations array
- **THEN** system SHALL not create any QuestionTranslation records for that question

### Requirement: Import option choice translations
The system SHALL create or update OptionChoiceTranslation records when importing a survey, regardless of whether the OptionGroup already exists.

#### Scenario: Import option choice with translations (new OptionGroup)
- **WHEN** survey.json option choice contains translations array
- **AND** the OptionGroup does not exist in the database
- **THEN** system SHALL create OptionGroup, OptionChoices, and OptionChoiceTranslation records

#### Scenario: Import option choice with translations (existing OptionGroup)
- **WHEN** survey.json option choice contains translations array
- **AND** the OptionGroup already exists in the database
- **THEN** system SHALL add missing OptionChoiceTranslation records to existing OptionChoices
- **AND** system SHALL update existing OptionChoiceTranslation records if language matches

#### Scenario: Import option choice without translations
- **WHEN** survey.json option choice has empty translations array
- **THEN** system SHALL not create any OptionChoiceTranslation records for that choice

### Requirement: Export session language
The system SHALL include selected language in responses.json session records.

#### Scenario: Session with language selected
- **WHEN** a session has `language = "ru"` is exported
- **THEN** responses.json session object SHALL include `"language": "ru"`

#### Scenario: Session without language selected
- **WHEN** a session has no language selected (single-language survey)
- **THEN** responses.json session object SHALL include `"language": null`

### Requirement: Import session language
The system SHALL restore session language when importing responses.

#### Scenario: Import session with language
- **WHEN** responses.json session contains `"language": "de"`
- **THEN** imported SurveySession SHALL have `language = "de"`

#### Scenario: Import session without language field
- **WHEN** responses.json session does not contain language field (legacy export)
- **THEN** imported SurveySession SHALL have `language = null`

## MODIFIED Requirements

### Requirement: Import creates related objects correctly
The import command SHALL create all related objects in the correct order to satisfy foreign key constraints.

#### Scenario: Import order
- **WHEN** a survey archive is imported
- **THEN** objects SHALL be created in this order:
  1. Organization (if specified and doesn't exist)
  2. OptionGroups and OptionChoices
  3. OptionChoiceTranslations
  4. SurveyHeader (with available_languages)
  5. SurveySections (without next/prev links)
  6. SurveySectionTranslations
  7. Questions (parents before children) with image extraction
  8. QuestionTranslations
  9. SurveySection next/prev links resolved

#### Scenario: Atomic import transaction
- **WHEN** import fails at any step
- **THEN** all created objects SHALL be rolled back and database remains unchanged
