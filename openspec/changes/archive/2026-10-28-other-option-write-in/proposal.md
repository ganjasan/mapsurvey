## Why

Creators who need an "Other" answer today build it from two questions: an "Other" option on
the choice question plus a separate text question gated by a visibility rule. That costs two
questions per "Other", exports the write-in as an unrelated column, and does not work at all
inside map popups, where sub-questions cannot carry visibility rules. Requested twice by a
research user (BC3, 2026-09-02 and 2026-09-16), the second time for a popup. Google Forms,
SurveyMonkey and Maptionnaire all ship it natively.

## What Changes

- A creator marks at most one option of a `choice` / `multichoice` question as the write-in
  option (`"other": true` on that option in `Question.choices`). The choices editor gets an
  "Other" column; the server keeps a single flag per question.
- Respondents who pick that option get a text field right under it, everywhere the question
  renders: section cards, dropdown style, sub-question popups on geo features, Objects-on-the-map
  popups, the editor's live preview. The field is hidden and disabled otherwise; picking the
  option focuses it. An empty write-in is allowed.
- The text is stored on the same `Answer` row as the selection, in the hitherto unused
  `Answer.text` of a choice answer, and only when the flagged option is among the selected codes.
  No migration.
- Exports gain one adjacent column per such question, `"<question name>: <option label>"`, in
  CSV, GeoJSON feature properties and the per-object CSV; the question's own column keeps the
  categorical label. Responses views show "label: text" inline. Public results and object
  aggregates keep bucketing "Other" by code and never carry the text.
- Revisit restores the write-in in all three places (top-level, geo popups, object popups);
  restoring now branches on `input_type` first, which also removes a latent misread of rows that
  carry both a selection and text.
- In passing: `addChoiceRow` in the question modal becomes a hoisted declaration, closing the
  `ReferenceError` PostHog captured on 2026-09-14 for star-rating questions; the GeoJSON
  sub-question export learns the dict cell shape that `ranking` already returns.

## Capabilities

### New Capabilities
- `other-option-write-in`: the write-in option end to end — flag, respondent field, storage
  rule, export columns, display, privacy boundary.

### Modified Capabilities
- `inline-choices`: choice objects may carry `other: true` on at most one entry; a choice answer
  may carry write-in text alongside its codes.
- `survey-editor`: the choices editor exposes the write-in flag and the modal script no longer
  aborts on star-rating questions.
- `answer-prepopulation`: revisits restore the write-in text for top-level fields and for geo
  sub-question popups, and choose the restored value by input type.
- `choice-dropdown-display`: the dropdown style renders the write-in field beneath the control
  and reveals it when the flagged option is chosen.

## Impact

`survey/other_option.py` (new), `survey/models.py`, `survey/forms.py`, `survey/views.py`,
`survey/analytics.py`, `survey/editor_views.py`, templates `partials/choice_option_other.html`
(new), `choice_dropdown.html`, `editor/partials/question_form_modal.html`,
`editor/partials/question_preview_frame.html`, `base_survey_template.html`,
`partials/layer_objects_block.html`, `survey/assets/js/other_option.js` (new), `survey/tests.py`.
Untouched by design: `public_results.py`, `object_stats.py`, `serialization.py` (ZIP already
round-trips the flag), `cloning.py`, `visibility.py`. AI generation keeps its strict choice
schema; AI drafts do not emit the flag until a follow-up adds it.
