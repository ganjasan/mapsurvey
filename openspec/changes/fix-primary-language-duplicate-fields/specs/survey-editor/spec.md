# Survey Editor — delta

## MODIFIED Requirements

### Requirement: Translation management
The system SHALL provide inline translation forms for sections (title, subheading) and
questions (name, subtext) for each **non-primary** language in the survey's
`available_languages` (every entry after the first). Translations SHALL be saved to
SurveySectionTranslation and QuestionTranslation models. No translation forms SHALL be
rendered for the primary language (the first entry) — its content is edited through the base
fields — and submitted `translation_<primary>_*` values SHALL be ignored on save. When the
survey has fewer than two available languages, no translation forms SHALL be displayed at
all. For surveys with two or more languages, base field labels SHALL name the primary
language (e.g. "Title (Português)") so the base field is identifiable as primary-language
content.

#### Scenario: Add Russian translation for a section title
- **WHEN** the survey has available_languages ["en", "ru"], the user enters a Russian title
  "Введение" for a section, and saves
- **THEN** a SurveySectionTranslation is created with language="ru" and title="Введение"

#### Scenario: No translation forms for single-language surveys
- **WHEN** the survey has available_languages ["es"] or empty available_languages
- **THEN** no translation form sections are displayed in the editor

#### Scenario: No translation form for the primary language
- **WHEN** the survey has available_languages ["pt", "es", "en"] and the user opens a section
  or question form
- **THEN** translation inputs are rendered for "es" and "en" only, and the base title/name
  labels identify Portuguese as the language being edited

#### Scenario: Stale primary-language translation POST is ignored
- **WHEN** a form submission includes `translation_pt_title` for a survey whose primary
  language is "pt"
- **THEN** no SurveySectionTranslation row with language="pt" is created or updated

### Requirement: Choices editor for choice-based questions
The system SHALL display a dynamic choices editor when the question's input_type is choice,
multichoice, range, or rating. The editor SHALL allow adding and removing choice rows. Each
row SHALL have a code (integer) and one name field per available language for multilingual
surveys, or a single name field for single-language surveys; the multilingual layout SHALL
include a column for the primary language and SHALL NOT render a separate "default" name
column. On save, choices SHALL be serialized to the `Question.choices` JSONField format: a
flat string name for single-language surveys, or a per-language dict containing every
non-empty column (primary included) for multilingual surveys. No entered name value SHALL be
silently discarded by serialization.

#### Scenario: Add choices to a new choice question
- **WHEN** the user creates a question with input_type "choice" on a single-language survey,
  adds two choices with codes 1 ("Yes") and 2 ("No"), and saves
- **THEN** the Question.choices field is set to `[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]`

#### Scenario: Multilingual choices
- **WHEN** the survey has available_languages ["en", "ru"] and the user adds a choice with
  code 1, en name "Yes", ru name "Да"
- **THEN** the choice is stored as `{"code": 1, "name": {"en": "Yes", "ru": "Да"}}`

#### Scenario: Primary-language column edit is preserved
- **WHEN** the survey has available_languages ["es", "en"] and the user edits the es column of
  an existing choice while the en column stays filled, and saves
- **THEN** the stored dict contains the edited es value and the existing en value — neither is
  discarded

#### Scenario: Remove a choice
- **WHEN** the user removes the second choice from a question with 3 choices
- **THEN** the choices JSONField is updated to contain only the remaining 2 choices

#### Scenario: Choices editor hidden for non-choice types
- **WHEN** the user selects input_type "text" or "point"
- **THEN** the choices editor is not displayed
