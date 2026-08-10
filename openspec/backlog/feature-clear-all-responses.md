# Clear all responses / reset survey data

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-04

## Description

There is no single action for "throw away everything collected so far and start testing again".
What exists today covers the need only partially:

- per-session trash, restore and hard delete in the responses view
  (`analytics_session_trash` / `analytics_session_restore` / `analytics_session_hard_delete`)
  — correct, but one row at a time
- a `clear_test_data` checkbox that deletes all sessions, available **only** on the
  `testing → published` transition (`survey/editor_views.py:1053-1057`)

So a creator who published directly from `draft`, or who wants to reset while still in `testing`,
has to delete each test session by hand. This is the recovery path people reach for after realising
their test data is unusable, which makes it more load-bearing than its priority suggests.

## Notes

- Asked for by: Manuel Frost (manu04, Berlin Senate) 2026-08-04 — "Maybe I need to clear all data
  an restart my Tests. Is there such a possibility?"
- Reuse the existing deletion path and the `clear_test_data` audit action rather than adding a
  second way to delete sessions.
- Guardrails: owner only; type-to-confirm on a survey with responses; never available on a
  `published` survey without an explicit second confirmation, since the same button on a live
  survey destroys real respondent data. Record it in the audit log with the deleted count, as the
  publish-time path already does.
- Related: [Deleting a question silently destroys all answers](bug-editing-question-destroys-answers.md)
  — that bug is why a creator ends up needing this.
- **2026-08-10 — partially shipped.** Bulk trash and hard-delete with select-all exist in analytics (`survey/analytics_views.py:408-422`, `analytics_dashboard.html:1175-1183`), and `clear_test_data` runs on the testing→published transition (`survey/editor_views.py:1297`). Missing: a single "clear all responses" action with type-to-confirm, independent of status.
