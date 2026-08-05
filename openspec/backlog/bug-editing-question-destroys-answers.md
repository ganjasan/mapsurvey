# Deleting a question silently destroys all answers already given to it

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-04

## Description

`Answer.question` is declared `on_delete=models.CASCADE` (`survey/models.py:616`). Deleting a
question from the editor therefore deletes every answer to it, across every session, with no
warning and no undo. The creator is told nothing before or after.

The user-visible symptom is an export that looks broken: sessions recorded before the edit come out
as empty rows carrying only `session`, `session_id`, `datetime`, `language` and
`validation_status`, while the last session — the one recorded after the final edit — has data.
The creator concludes the export is faulty, not that their own editing removed the data.

This is the counterpart of the read-only lock on published surveys: a *published* survey is
protected by versioning, but a survey in `draft` or `testing` — exactly the state in which people
iterate while collecting first responses — has no protection at all.

## Notes

- **2026-08-05 — FIXED** in change `warn-before-destroying-answers`, branch
  `fix/question-delete-destroys-answers`. The cascade is unchanged; what changed is that a delete
  which would destroy answers is refused until the author acknowledges the count, and the
  confirmation explains what versioning would have preserved. Soft-delete was considered and
  rejected: it needs new state on `Question`, a migration, and export and analytics changes, which
  is disproportionate for data belonging to surveys nobody has published.
- Exposure, measured on production 2026-08-05 and worth keeping because it sized the fix:
  **50 surveys in `draft` holding 842 answers, 12 in `testing` holding 1471.** Published and closed
  surveys are protected twice over — by the read-only lock on structural edits, and by versioning
  moving the previous structure and sessions onto an archived header rather than deleting them
  (`versioning.py:236-260`). That is not theory: 61 archived headers currently hold 1060 questions
  and 3466 answers.
- Reported by: Manuel Frost (manu04, Berlin Senate) 2026-08-04 — "I entered some test data into my
  test project, but upon export, only the last answer contains data; the rest are empty. I think
  you have changed some things and my data are older." His own reading was right; the trigger was
  his editing, not a deploy.
- Root cause confirmed by reading the FK declaration and the export path. **Not** confirmed against
  his production rows — the prod DB query was not run, so "his sessions are empty for this reason"
  remains inference from code.
- Decide the intended behaviour before implementing; the options are not equivalent:
  - warn on delete when `Answer.objects.filter(question=...).exists()`, showing the count
  - soft-delete the question and keep its answers exportable as a historical column
  - keep CASCADE but block deletion outright once answers exist, offering "hide" instead
- The same question applies to editing a question's `input_type` or removing choice codes — the
  versioning compatibility checker (`check_draft_compatibility()`) already reasons about exactly
  these cases for published surveys. Reuse that logic rather than inventing a second set of rules.
- Related: [Clear all responses / reset survey data](feature-clear-all-responses.md) — the recovery
  path for a creator who has already hit this.
