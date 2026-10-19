## MODIFIED Requirements

### Requirement: Display style serialization
Question objects in `survey.json` SHALL include the `display_style` key, and the survey object SHALL include the `style_settings` key. Import SHALL accept archives that lack these keys or carry unknown values in them. It SHALL fall back to `display_style = "default"` and `style_settings = {}`, which preserves the prior rendering behavior.

The known values per question type SHALL be those of the one display-style table:

- `choice`: `default`, `dropdown`, `icon_grid`
- `multichoice`: `default`, `icon_grid`
- `rating`: `default`, `scale_strip`, `list_pips`, `stars`

A known value SHALL survive export→import unchanged. A value not known for the question's type SHALL fall back to `default`. `stars` SHALL also be a known `style_settings.rating_display_style`, matching what the editor offers.

The optional `icon` and `group` keys on choice entries SHALL round-trip unchanged, subject only to the inline-choices cleanup.

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

#### Scenario: Icon grid with icons and groups round-trips
- **WHEN** a survey with an icon-grid multichoice question whose choices carry `icon` and `group` is exported and re-imported
- **THEN** the imported question has `display_style = "icon_grid"` and identical choice entries

#### Scenario: Pre-change archive imports unchanged
- **WHEN** an archive exported before this change is imported
- **THEN** every choice, multichoice and rating question's `display_style` and `choices` equal what the same import produced before this change, and every question renders as before (a rating style stored on another type, which never took effect, is imported as `default`)
