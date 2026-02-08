# Survey Content Translation

This spec defines how survey content (sections, questions, option choices) is translated into multiple languages.

## ADDED Requirements

### Requirement: Survey defines available languages
The system SHALL allow each survey to define a list of available languages for respondents.

#### Scenario: Survey with multiple languages
- **WHEN** a survey has languages configured (e.g., "en", "ru", "de")
- **THEN** the survey MUST store the list of available language codes

#### Scenario: Survey without translations
- **WHEN** a survey has no languages configured
- **THEN** the survey MUST be treated as single-language (original content only)

### Requirement: Section content is translatable
The system SHALL store translations for SurveySection fields: `title` and `subheading`.

#### Scenario: Section translation exists
- **WHEN** a section has a translation for the selected language
- **THEN** the translated `title` and `subheading` MUST be returned

#### Scenario: Section translation missing
- **WHEN** a section has no translation for the selected language
- **THEN** the original (untranslated) `title` and `subheading` MUST be returned

### Requirement: Question content is translatable
The system SHALL store translations for Question fields: `name` and `subtext`.

#### Scenario: Question translation exists
- **WHEN** a question has a translation for the selected language
- **THEN** the translated `name` and `subtext` MUST be returned

#### Scenario: Question translation missing
- **WHEN** a question has no translation for the selected language
- **THEN** the original (untranslated) `name` and `subtext` MUST be returned

### Requirement: Option choice content is translatable
The system SHALL store translations for OptionChoice field: `name`.

#### Scenario: Option choice translation exists
- **WHEN** an option choice has a translation for the selected language
- **THEN** the translated `name` MUST be returned

#### Scenario: Option choice translation missing
- **WHEN** an option choice has no translation for the selected language
- **THEN** the original (untranslated) `name` MUST be returned

### Requirement: Translation storage is separate from original models
The system SHALL store translations in dedicated translation models linked to the original entities via foreign keys.

#### Scenario: Translation model structure
- **WHEN** translations are stored
- **THEN** each translation model MUST have: a foreign key to the original entity, a language code field, and translated content fields

#### Scenario: Multiple translations per entity
- **WHEN** an entity (section, question, option choice) has translations
- **THEN** there MUST be at most one translation record per language per entity

### Requirement: Translations are manageable via admin interface
The system SHALL provide inline forms in Django admin for managing translations.

#### Scenario: Admin inline for section translations
- **WHEN** editing a SurveySection in admin
- **THEN** translation inline forms MUST be available for adding/editing translations

#### Scenario: Admin inline for question translations
- **WHEN** editing a Question in admin
- **THEN** translation inline forms MUST be available for adding/editing translations

#### Scenario: Admin inline for option choice translations
- **WHEN** editing an OptionChoice in admin
- **THEN** translation inline forms MUST be available for adding/editing translations

### Requirement: Language codes follow ISO 639-1 standard
The system SHALL use ISO 639-1 two-letter language codes (e.g., "en", "ru", "de", "fr").

#### Scenario: Valid language code
- **WHEN** a language code is stored
- **THEN** it MUST be a valid ISO 639-1 two-letter code
