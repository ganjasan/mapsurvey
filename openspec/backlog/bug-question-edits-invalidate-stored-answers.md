# Editing a question's type or choices invalidates stored answers, unwarned

**Type**: bug
**Priority**: medium
**Area**: backend
**Created**: 2026-08-05

## Description

Deleting a question is not the only edit that costs collected answers. Changing a question's
`input_type`, or removing choice codes that stored answers reference, leaves those answers in place
but no longer meaningful: a `choice` answer holding code `3` after code `3` is removed exports as
the bare number, and a `number` answer under a question that is now `text` is read by neither the
export nor the analytics path that matches on type.

The platform already knows how to detect exactly this. `check_draft_compatibility(draft, canonical)`
reports `changed_input_type` and `removed_choice_codes` with the affected answer counts, and
publishing a draft refuses on them unless forced. But that check only runs on the published path —
a survey that has never been published can be edited this way with no warning at all, which is the
same asymmetry that [deleting a question](bug-editing-question-destroys-answers.md) had.

## Notes

- Found 2026-08-05 while implementing `warn-before-destroying-answers`, and deliberately left out of
  it to keep that change to deletion. Recorded there as an open question in `design.md`.
- The detection exists; what is missing is calling it on the unpublished path and surfacing the
  result. That makes this considerably cheaper than it looks — likely the same 409-plus-count shape
  the delete guard now uses, reusing `check_draft_compatibility`'s issue list instead of a count.
- Worth deciding at the same time whether the answer is to warn or to migrate the stored answers
  where it is safe to (renaming a choice is harmless; removing one is not). Warning first is the
  smaller step and matches what the delete guard does.
- Unlike deletion, this one is silent *after* the fact too: nothing is missing from the editor, so a
  creator has no reason to suspect anything until the export looks wrong.
