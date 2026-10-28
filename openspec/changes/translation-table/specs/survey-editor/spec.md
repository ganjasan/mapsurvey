# Survey Editor — delta

## MODIFIED Requirements

### Requirement: Translation management
The system SHALL show, in the section, question and group modals, a read-only Translations block
for each **non-primary** language in the survey's `available_languages` (every entry after the
first) with the stored translations of that entity (section: title, subheading, Next-button label;
question: name, subtext; group: title, description). The fields SHALL be disabled; each SHALL link
to the Translations tab opened on that language and scrolled to the entity's row, and the block
SHALL say that translations are edited there. Submitted `translation_<lang>_*` values SHALL be
ignored by the modal save paths; translations SHALL be written only through the Translations tab,
its CSV import, and the API/MCP services. No block SHALL be rendered for the primary language (its
content is edited through the base fields). When the survey has fewer than two available languages,
no Translations block SHALL be displayed. For surveys with two or more languages, base field labels
SHALL name the primary language (e.g. "Title (Português)").

#### Scenario: Open a translation from the question modal
- **WHEN** the survey has available_languages ["en", "ru"], a question has the Russian name "Введение", and the user opens the question modal
- **THEN** the Translations block shows "Введение" in a disabled field, and clicking it opens the Translations tab on Russian at that question's row

#### Scenario: Stale translation POST is ignored
- **WHEN** a form submission to the section or question endpoint includes `translation_ru_title` or `translation_pt_title`
- **THEN** no SurveySectionTranslation or QuestionTranslation row is created or updated by that request

#### Scenario: No translation block for single-language surveys
- **WHEN** the survey has available_languages ["es"] or empty available_languages
- **THEN** no Translations block is displayed in the editor

#### Scenario: No translation block for the primary language
- **WHEN** the survey has available_languages ["pt", "es", "en"] and the user opens a section or question form
- **THEN** read-only translation fields are rendered for "es" and "en" only, and the base title/name labels identify Portuguese as the language being edited

### Requirement: Choices editor for choice-based questions
The system SHALL display a dynamic choices editor when the question's input_type is choice,
multichoice, range, or rating. The editor SHALL allow adding and removing choice rows. Each
row SHALL have a code (integer) and, for multilingual surveys, one name field per available
language — the primary language's field editable, every other language's field read-only and
linking to the Translations tab at that option's row — or a single name field for single-language
surveys; the multilingual layout SHALL include a column for the primary language and SHALL NOT
render a separate "default" name column. On save, choices SHALL be serialized to the
`Question.choices` JSONField format: a flat string name for single-language surveys, or a
per-language dict for multilingual surveys that keeps every stored non-primary name unchanged and
contains the submitted primary name. No entered name value SHALL be silently discarded by
serialization.

#### Scenario: Add choices to a new choice question
- **WHEN** the user creates a question with input_type "choice" on a single-language survey,
  adds two choices with codes 1 ("Yes") and 2 ("No"), and saves
- **THEN** the Question.choices field is set to `[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]`

#### Scenario: Multilingual choices
- **WHEN** the survey has available_languages ["en", "ru"], a choice with code 1 has the names `{"en": "Yes", "ru": "Да"}`, and the user edits the en name to "Yes, please" and saves
- **THEN** the choice is stored as `{"code": 1, "name": {"en": "Yes, please", "ru": "Да"}}`

#### Scenario: Non-primary column opens the table
- **WHEN** the survey has available_languages ["es", "en"] and the user clicks the en field of an existing choice
- **THEN** the Translations tab opens on English scrolled to that option's row

#### Scenario: Remove a choice
- **WHEN** the user removes the second choice from a question with 3 choices
- **THEN** the choices JSONField is updated to contain only the remaining 2 choices

#### Scenario: Choices editor hidden for non-choice types
- **WHEN** the user selects input_type "text" or "point"
- **THEN** the choices editor is not displayed
