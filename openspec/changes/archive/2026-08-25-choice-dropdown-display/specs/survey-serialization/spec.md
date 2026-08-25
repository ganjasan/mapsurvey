# survey-serialization Delta Specification

## MODIFIED Requirements

### Requirement: Display style serialization
Question objects in `survey.json` SHALL include the `display_style` key, and the survey
object SHALL include the `style_settings` key. Import SHALL accept archives without these
keys (or with unknown values) by falling back to `display_style = "default"` and
`style_settings = {}` — preserving prior rendering behavior. For `choice` questions,
`dropdown` SHALL be a known `display_style` value that survives export→import unchanged;
on non-choice questions `dropdown` SHALL be treated as unknown and fall back to
`default`.

#### Scenario: Export includes display style and style settings
- **WHEN** a survey with `style_settings.rating_display_style = "list_pips"` containing a rating question with `display_style = "scale_strip"` is exported
- **THEN** `survey.json` contains `"style_settings": {"rating_display_style": "list_pips"}` on the survey object and `"display_style": "scale_strip"` on the question object

#### Scenario: Import of legacy archive defaults the style
- **WHEN** a `survey.json` produced before this change (no `display_style` / `style_settings` keys) is imported
- **THEN** imported rating questions get `display_style = "default"` and the survey gets empty `style_settings` (effective rendering: scale strip)

#### Scenario: Dropdown style round-trips on a choice question
- **WHEN** a survey containing a choice question with `display_style = "dropdown"` is exported and re-imported
- **THEN** the imported choice question has `display_style = "dropdown"`

#### Scenario: Dropdown on a non-choice question falls back
- **WHEN** an archive contains a text question with `display_style = "dropdown"`
- **THEN** the imported question gets `display_style = "default"`
