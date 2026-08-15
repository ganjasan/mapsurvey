# Subtext is offered on every question type and rendered on four

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-08-15

## Description

The question editor offers **Subtext** for every `input_type`. It reaches the respondent on four
of thirteen. On the other nine the creator types it, saves, sees no complaint, and respondents
never see it — the same failure shape as
[Color/Icon/Image on every type](bug-question-fields-shown-for-every-type.md), which is fixed.

Measured on a published survey with one question of every type, each carrying a distinct marker
string, fetched over HTTP (not in a preview):

| type | Name / text | Subtext |
|---|---|---|
| text, text_line, number | shown | **dropped** |
| choice, multichoice | shown | **dropped** |
| range, rating | shown | **dropped** |
| datetime | shown | **dropped** |
| point, line, polygon | shown | shown |
| html (Formatted Text) | **dropped** | shown |
| image | **dropped** | **dropped** |

## Cause

`SurveySectionAnswerForm._get_form_from_input_type` (`survey/forms.py`) takes a `sublabel`
argument and passes it on for exactly four branches: the three geo types
(`subtitle=sublabel` on the draw button) and `html`. Every other branch accepts the argument and
discards it, and no template renders `question.subtext` for those types.

Two smaller gaps fall out of the same table:

- **`html` drops the Name.** `HTMLField` gets `title=label`, but `html_text.html` renders only
  `{{ widget.subtitle }}`. A creator who titles a Formatted Text block never sees that title.
- **`image` drops both.** `show_image.html` renders the `<img>` and nothing else, so an image
  block cannot be captioned at all.

## Notes

- Found 2026-08-15 while reviewing the live preview in the question dialog: the subtext typed
  into the dialog did not appear in the preview, which turned out to be truthful — it does not
  appear in the survey either.
- Decide the intent per type rather than blanket-rendering: subtext under an ordinary question is
  a helper line and belongs above the input; for `image` it is a caption; for `html` the Name may
  legitimately stay hidden (the block *is* its content), in which case the field should be hidden
  in the dialog instead — the per-type visibility machinery from
  [the type picker rework](improvement-group-question-type-list.md) is already there to do it.
- Check the same question for the editor's own preview and the public results page.
- Not fixed inside `star-rating-display`: unrelated scope, and the fix needs a per-type decision
  plus a template pass.

- **2026-08-15 — fixed** in change `subtext-rendering`: subtext now renders for all eight answerable types (between the question text and the input) and as a caption on image blocks. The Name stays hidden on `image` and `html` by decision, not by accident — it is the block identifier in the editor and published surveys use internal labels there. A table test over every input type pins the whole mapping.
