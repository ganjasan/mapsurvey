## Why

The popup that opens on a placed feature, and the object popup of "Objects on the map", render
their sub-questions with Django's `Form.as_p()` (#320). That drops the creator's hint (it lives on
the widget, not in `help_text`): 111 sub-questions with a hint across 36 published surveys show
nothing. It also renders a rating sub-question as bare radios instead of the strip, pips or stars
the creator picked, and loses the card layout of the section form. The `question-subtext` spec
already promises the hint for every question that collects an answer.

## What Changes

- The section form's per-field card loop moves to `partials/question_fields.html`; the section
  form, the sub-question popups (`views.section` → `subquestions_forms`) and the editor's question
  preview all render through it.
- A popup initialises what only initialised on page load or an htmx swap: ranking
  (`window.initRanking`) and the rating strip chip (`window.syncRatingChips`), through one
  `window.initPopupFields(root)` called after stored answers are restored, in both popups.
- Inside a popup, cards drop their frame (the popup is the frame) and stack with a rule between
  them, and blocks take the section's base font size instead of Leaflet's 12px.

## Capabilities

### New Capabilities

### Modified Capabilities
- `question-subtext`: sub-questions show their hint and display style in the map popup.

## Impact

`survey/views.py` (popup forms), `partials/question_fields.html` (new),
`partials/survey_section_partial.html`, `editor/partials/question_preview_frame.html`,
`base_survey_template.html`, `partials/layer_objects_block.html`, `js/components/ranking.js`,
`css/main.css`. No model, migration or answer-format change: the popup JS reads and writes fields
by `name`, which the cards keep.
