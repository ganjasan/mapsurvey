# Survey Content Translation — delta

## ADDED Requirements

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
