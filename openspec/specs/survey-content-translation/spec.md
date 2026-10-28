# Survey Content Translation

## Purpose
This spec defines how survey content (sections, questions, option choices) is translated into multiple languages.

## Requirements
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

### Requirement: Primary language content lives in base fields only
The first entry of a survey's `available_languages` SHALL be its primary language. Primary-
language content SHALL be stored exclusively in base model fields (`SurveySection.title`/
`subheading`, `Question.name`/`subtext`); translation rows SHALL exist only for non-primary
languages. The system SHALL NOT create `SurveySectionTranslation` or `QuestionTranslation`
rows for the primary language, and save paths SHALL ignore submitted primary-language
translation values.

#### Scenario: Single-language survey has no translation rows
- **WHEN** a survey has `available_languages` `["es"]` and its content is edited and saved
- **THEN** no translation rows exist for any of its sections or questions, and respondents
  see the base field text

#### Scenario: Multilingual survey stores primary in base only
- **WHEN** a survey has `available_languages` `["pt", "es", "en"]`
- **THEN** Portuguese content lives in base fields, translation rows exist only for `es` and
  `en`, and a POSTed `translation_pt_*` value is ignored

#### Scenario: Legacy primary-language rows are folded into base
- **WHEN** the data migration runs against a survey whose sections or questions carry
  primary-language translation rows
- **THEN** each non-empty translated field value replaces the corresponding base field value,
  the primary-language rows are deleted, and the text resolved for a primary-language
  respondent is identical before and after the migration

### Requirement: Choice names carry the primary language in their base slot
Choice `name` values SHALL be a flat string for single-language surveys and a per-language
dict for multilingual surveys, in which the primary language key holds the base text. The
data migration SHALL normalize legacy shapes: dict names on single-language surveys are
flattened to the value currently resolved for the primary language, and multilingual dict
names missing the primary key gain it with the currently-resolved value.

#### Scenario: Single-language dict name flattened
- **WHEN** the migration encounters `{"code": 1, "name": {"es": "Sí"}}` on a survey with
  `available_languages` `["es"]`
- **THEN** the choice becomes `{"code": 1, "name": "Sí"}`

#### Scenario: Multilingual dict gains missing primary key
- **WHEN** the migration encounters a choice name dict without the primary-language key on a
  multilingual survey
- **THEN** the primary key is added with the value `get_choice_name` resolves for the primary
  language today, and all other keys are unchanged
