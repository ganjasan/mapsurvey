# Rating Question Display Style

## Why

Rating questions with worded Likert options currently render as flex-wrap pill buttons. Five options of unequal width break into a ragged 2-2-1 grid in the 420px survey panel: the scale order reads zigzag, the widest option looks like a primary button, and long labels (e.g. German "sehr zuversichtlich") make it worse. A mockup review settled on two good renderers — a compact numeric scale strip and a vertical list with intensity pips — and survey creators should be able to pick per question.

## What Changes

- New `Question.display_style` field with three values for `rating` questions:
  - `default`: inherit the survey-level default style.
  - `scale_strip`: one row of equal numbered cells, anchor labels (first/last option) under the row, selected option's full label appears as a chip below.
  - `list_pips`: vertical list of full-width option rows, each with a right-aligned intensity pip indicator (n of N filled).
- New `SurveyHeader.style_settings` JSON field holding survey-wide style defaults; first key `rating_display_style` (`scale_strip` if unset). Extensible container for future appearance settings (fonts, palettes, sidebar position — out of scope, captured as follow-up).
- Existing flex-wrap pill rendering for rating questions is replaced — every rating question renders as one of the two visual styles (existing questions inherit the survey default, which is `scale_strip` unless changed).
- Editor question modal gets a "Display as" picker (Survey default / Compact scale / Labeled list), visible only when input type is `rating`; the modal's live preview reflects the picked style immediately, before saving.
- Survey settings page gets a "Style" section with the survey-wide default rating style.
- Survey serialization exports/imports `display_style` and `style_settings`; imports of older archives keep prior behavior.
- Versioning draft clone copies `display_style` and `style_settings`.

## Capabilities

### New Capabilities

- `rating-display-style`: How rating questions render for respondents — the two display styles, their selection/hover states, the default, and the fallback behavior.

### Modified Capabilities

- `survey-editor`: Question CRUD requirement gains a "Display as" control for rating questions in the question modal.
- `survey-serialization`: Question serialization format gains the `display_style` key with a backward-compatible import default.

## Impact

- `survey/models.py` — new `Question.display_style` field + migration.
- `survey/forms.py` — rating branch of `SurveySectionAnswerForm._get_form_from_input_type` picks a widget/renderer by `display_style`.
- `survey/templates/` + `survey/assets/css/main.css` + small JS — two renderers per the approved mockup (`rating-question.mockup.html` in this change folder); current `.question-card--rating` flex-wrap CSS replaced.
- `survey/editor_forms.py`, `survey/templates/editor/partials/question_form_modal.html` — "Display as" picker.
- `survey/serialization.py` — export/import of `display_style`.
- `survey/versioning.py` — `clone_survey_for_draft()` copies the field.
