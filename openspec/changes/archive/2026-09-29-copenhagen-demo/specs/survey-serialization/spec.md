## MODIFIED Requirements

### Requirement: Display style serialization
Question objects in `survey.json` SHALL include the `display_style` key, and the survey object SHALL include the `style_settings` key. Import SHALL accept archives without these keys (or with unknown values) by falling back to `display_style = "default"` and `style_settings = {}` — preserving prior rendering behavior. For `choice` questions, `dropdown` SHALL be a known `display_style` value that survives export→import unchanged; on non-choice questions `dropdown` SHALL be treated as unknown and fall back to `default`. `stars` SHALL be a known `display_style` on non-choice questions and a known `style_settings.rating_display_style`, matching what the editor offers.

#### Scenario: Export includes display style and style settings
- **WHEN** a survey with `style_settings.rating_display_style = "list_pips"` containing a rating question with `display_style = "scale_strip"` is exported
- **THEN** `survey.json` contains `"style_settings": {"rating_display_style": "list_pips"}` on the survey object and `"display_style": "scale_strip"` on the question object

#### Scenario: Import of legacy archive defaults the style
- **WHEN** a `survey.json` produced before this change (no `display_style` / `style_settings` keys) is imported
- **THEN** imported rating questions get `display_style = "default"` and the survey gets empty `style_settings` (effective rendering: scale strip)

#### Scenario: Import rejects garbage values safely
- **WHEN** a hand-edited `survey.json` contains `"display_style": "fancy"` or a non-dict / unknown-valued `style_settings`
- **THEN** the survey imports successfully with `display_style = "default"` and the invalid `style_settings` content dropped

#### Scenario: Round-trip preserves the style
- **WHEN** a survey with a `list_pips` rating question and a `list_pips` survey default is exported and re-imported
- **THEN** the re-imported question keeps `display_style = "list_pips"` and the survey keeps `style_settings.rating_display_style = "list_pips"`

#### Scenario: Stars round-trip
- **WHEN** a survey with a `stars` rating question and a `stars` survey default is exported and re-imported
- **THEN** the re-imported question keeps `display_style = "stars"` and the survey keeps `style_settings.rating_display_style = "stars"`

#### Scenario: Dropdown style round-trips on a choice question
- **WHEN** a survey containing a choice question with `display_style = "dropdown"` is exported and re-imported
- **THEN** the imported choice question has `display_style = "dropdown"`

#### Scenario: Dropdown on a non-choice question falls back
- **WHEN** an archive contains a text question with `display_style = "dropdown"`
- **THEN** the imported question gets `display_style = "default"`

## ADDED Requirements

### Requirement: Shared-map layer label survives a code remap
When an import remaps question codes, a `question`-sourced layer's `label_field` (the sub-question whose answer titles each mark) SHALL be remapped together with its `source_question_code`.

#### Scenario: Import into a database that already holds the codes
- **WHEN** an archive with a shared-map layer whose `label_field` names a sub-question code is imported where that code already exists
- **THEN** the imported layer's `label_field` SHALL be the remapped code of the imported sub-question, and marks materialised from it SHALL carry that sub-answer as their title
