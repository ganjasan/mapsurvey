# Survey Serialization — Delta

## ADDED Requirements

### Requirement: Display style serialization
Question objects in `survey.json` SHALL include the `display_style` key, and the survey object SHALL include the `style_settings` key. Import SHALL accept archives without these keys (or with unknown values) by falling back to `display_style = "default"` and `style_settings = {}` — preserving prior rendering behavior.

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
