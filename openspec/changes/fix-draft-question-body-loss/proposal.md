# fix-draft-question-body-loss

## Why

A draft question is deleted when the modal closes unless it has a name — and "has a name" is
the whole test. Write the question's body into Subtext, leave Name empty, close: autosave has
already stored the text, and the close handler deletes the row anyway.

The rule is inconsistent with itself. The same change that introduced the draft row
(`fix-new-question-modal-layout`) deliberately carries **Name and Subtext** onto the row at
type pick, because "Name and Subtext are typed before the type as often as after". One code
path treats subtext as work worth keeping; the other does not count it at all.

It lands hardest on the **Formatted Text (`html`)** block, where `Question.name` is an
editor-only label that never reaches a respondent and `subtext` IS the whole body
(`question-subtext` spec). A creator writing a text block has every reason to leave the name
blank, so the case that loses the work is the ordinary one, not a corner.

The same sentence covers a second path. Before a type is picked there is no row at all, so
closing the modal with Name or Subtext already typed dropped the text without a word — and the
fields sit ABOVE the picker (`fields = ['name', 'subtext', 'input_type', ...]`), so typing
first is the layout's own suggestion.

Reported by a customer on 2026-09-17 — "I've written up survey questions that I then realized
weren't saved or hit close and they disappear" — in a letter that opens by calling Mapsurvey
"a very early stage product". Backlog #179 and #180.

## What Changes

Emptiness stops meaning "no name" and starts meaning "nothing was written or configured".
Both halves of the check gain subtext:

- `editor/survey_detail.html`, the `hidden.bs.modal` handler: keep the draft when the
  `subtext` input has content. Quill already normalises an empty editor to `''`
  (`input.value = (h === '<p><br></p>') ? '' : h`), so a trimmed truth test is enough.
- `editor_views.py::editor_question_delete`, the `if_empty` guard: add subtext to
  `configured`, with tags stripped so markup that carries no text (`<p><br></p>`, a stray
  `&nbsp;`) still counts as empty.

Closing before a type is picked stops discarding too. When Name or Subtext carries anything,
the close saves it the same way the picker would, defaulting the type to `text`; the creator
finds their words in the section and changes the type there. The picker itself still opens
with nothing lit — a pre-selected tile would read as a choice already made, which is why the
default is applied at close rather than shown up front (owner decision, 2026-09-18).

Unchanged: a genuinely untouched draft is still discarded on close, and an untouched create
modal still creates nothing — which is what keeps abandoned rows out of the section list.

## Capabilities

### Modified Capabilities

- `survey-editor`: a draft question survives the modal closing when any of name, subtext,
  layer or sub-questions is present — not name alone; and closing before a type is picked
  saves what was typed as a `text` question instead of discarding it.

## Impact

- `survey/templates/editor/survey_detail.html`, `survey/editor_views.py`, `survey/tests.py`,
  `tests_e2e/test_question_draft_body_loss.py`. No migration, no kill switch.
- The close handlers are browser behaviour the Django test client cannot see, so the browser
  half is covered by Playwright against a running dev server.
- **Archive order**: the requirement this modifies lives in the unarchived change
  `fix-new-question-modal-layout` and is not yet in `openspec/specs/survey-editor/spec.md`.
  That change must be archived first, or this delta has nothing to modify.
