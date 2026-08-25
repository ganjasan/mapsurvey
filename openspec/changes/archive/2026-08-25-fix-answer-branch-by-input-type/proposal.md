# Fix: answer saving dispatches on stale `choices`, 500-ing geo submits

## Why

The respondent POST handler in `survey_section` decides how to store an answer by whether
`question.choices` happens to be non-empty (`if not question.choices:` at `survey/views.py:935`,
and again for sub-questions at `:969`) — not by `input_type`. A question whose type was switched
in the editor can keep its old `choices` list: the edit view clears choices only when the posted
`choices_json` is empty, but the choices widget keeps that hidden field populated across a type
switch, so switching e.g. choice → point writes the stale list right back. Such a poisoned
point question routes its GeoJSON payload into the choice branch — `int('{"type":"Feature"...')` —
`ValueError`, an unhandled 500 on every submit of the section.

This is what actually broke creator adorion@cabinworks.ca's "Finish doesn't submit" survey on
2026-08-24 (PostHog exceptions show the exact ValueError with her question `Q_7633107523`,
a `point` with 6 leftover choices). She deleted the survey and rebuilt it from scratch.
Production has **10 poisoned geo questions across 4 creators**; three other creators' surveys
(ids 150, 159, 217) are drafts that will 500 on their first published submit.

The same broken dispatch silently loses data in another branch: a `datetime` question (top-level
or sub-question) matches no storage arm and saves an **empty** Answer row — the value is dropped,
while prepopulation and analytics expect it in `answer.text`. Adorion's live Crime Watch survey
has a Date/Time sub-question collecting nothing right now.

## What Changes

- **Answer storage dispatches on `input_type`** — top-level and sub-question branches both:
  geo → geometry, ranking → permutation check, choice/multichoice/rating → `selected_choices`,
  number/range → `numeric`, text/text_line/datetime → `text`. `choices` content no longer
  selects a branch.
- **`datetime` values persist** to `answer.text` (both levels) instead of being dropped.
- **The editor clears `choices` on save whenever the type doesn't use them** (create, edit and
  sub-question-create paths) — regardless of what `choices_json` was posted. Types that keep
  choices: `choice`, `multichoice`, `range`, `rating`, `ranking` (new `CHOICE_TYPES` constant in
  `survey/question_types.py`).
- **ZIP import normalizes the same way**, so a poisoned export cannot recreate the state.
- **A data migration clears `choices`** on every existing question whose type doesn't use them —
  this repairs the 10 poisoned rows in production (defense in depth: the dispatch fix alone
  already makes them harmless).

Not in scope: validating that submitted choice codes exist in `choices` (pre-existing behavior),
and any change to how the choices editor UI posts `choices_json`.
