# Subtext reaches the respondent

## Why

The question editor offers **Subtext** for every input type and delivers it on four of thirteen.
Measured on a published survey carrying one question of every type, fetched over HTTP:

| type | Name / text | Subtext |
|---|---|---|
| text, text_line, number, choice, multichoice, range, rating, datetime | shown | **dropped** |
| point, line, polygon | shown | shown |
| html (Formatted Text) | **dropped** | shown |
| image | **dropped** | **dropped** |

`_get_form_from_input_type` takes a `sublabel` argument and forwards it in four branches — the
three geo types and `html`. The other nine accept it and discard it, and no template renders
`question.subtext` for them. A creator writes a clarifying line under their question, saves,
sees no complaint, and respondents never see it.

This is the same failure shape as backlog #111 (Color/Icon/Image offered on every type, consumed
by few), which is fixed: a field that is offered must either work or not be offered.

Found while reviewing the question dialog's new live preview — the subtext was missing from the
preview, and the preview turned out to be telling the truth.

## What Changes

- **Subtext renders for every type that collects an answer** — text, text_line, number, choice,
  multichoice, range, rating, datetime — as a helper line between the question text and the
  input, where a respondent reads it before answering.
- **Image blocks get a caption.** `image` currently renders the picture and nothing else;
  subtext becomes its caption.
- **Geo types and Formatted Text are unchanged** — they already deliver subtext.
- **The Name stays hidden on `image` and `html`.** It is the block's identifier in the editor,
  not respondent-facing copy, and surveys in the wild carry names like `html_block_1`; rendering
  them now would leak internal labels into live surveys. Recorded as a decision rather than left
  as an accident.

No model change, no migration: `Question.subtext` already exists and is already saved. Existing
surveys begin showing text their creators wrote and expected to be visible — the fix is
deliberately visible, and worth stating in a release note.

## Capabilities

### New Capabilities

- `question-subtext`: where a question's subtext appears for the respondent, per input type,
  including the types that deliberately do not show it.

## Impact

- `survey/forms.py` — carry `sublabel` onto the widget for answerable types; pass it to
  `ShowImageField` for the caption.
- `survey/templatetags/question_utils.py` — `question_subtext` filter.
- `survey/templates/partials/survey_section_partial.html`,
  `survey/templates/editor/partials/question_preview_frame.html` — render the helper line.
- `survey/templates/show_image.html` — caption.
- `survey/assets/css/main.css` — one block; collectstatic.
- `survey/tests.py` — a per-type table test, so the next type added cannot quietly drop it.
- Closes backlog #123. Stacked on `feature/star-rating-display` (#64): both edit the same form
  branch and the same section template.
