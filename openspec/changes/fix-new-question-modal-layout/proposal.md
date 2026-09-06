# fix-new-question-modal-layout

## Why

Since PR #160 ("questions are created on type pick") the "New question" modal is a
stripped-down type picker: no Name, no Subtext, no right-hand column, the tile grid
stretched over the full dialog width. The moment a type is picked the modal re-renders as
the edit modal — Name and Subtext appear above the picker, the preview column pushes in
from the right, and the tiles reflow from ten per row to six. The owner reported this as
the dialog "jerking" (2026-09-06, two screenshots).

Name and Subtext exist for every question type, and so does the "Respondent sees" column.
Nothing above or beside the type picker depends on the type; only what is below it does.
Hiding them in the first step buys nothing and costs a layout jump on every new question.

## What Changes

- The "New question" modal renders the same shell as the edit modal: Name, Subtext, the
  Input type picker and the preview column are all present from the start. Only the
  type-scoped area below the picker (choices editor, layer picker, validation,
  translations, visibility, sub-questions) and the Create button stay hidden until a type
  is picked.
- Picking a type still creates the row (unchanged mechanics from PR #160) but carries the
  Name and Subtext typed so far, so nothing the creator typed before choosing a type is
  lost. A draft that already has a name is a named question — no draft marker, so closing
  the modal keeps it.
- Title reads "New Question" again — there is no separate "pick a type" step to name.

## Capabilities

### Modified Capabilities

- `survey-editor`: "Question rows are created on type pick" — the New question modal is
  the full question shell; type pick creates the row with the name/subtext typed so far.

## Impact

- `survey/templates/editor/partials/question_form_modal.html` (create-mode CSS, title,
  type-pick POST payload), `survey/editor_views.py` (`editor_question_create` draft path
  accepts `name`/`subtext`, subtext through `coerce_creator_html`), `survey/tests.py`.
- No migration.
