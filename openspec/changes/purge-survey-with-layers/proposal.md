## Why

A creator pressed **Delete forever** on a trashed survey ten times over two days and got a
500 every time. PostHog issue `01a0a513-…`: ten `ProtectedError`s from
`purge_survey_view → trash.purge_survey`, all on
`POST /editor/purge/8725ebde-069c-4fbb-8ae1-1c482327baed/`, 2026-09-15 and 2026-09-16.

The survey was already in Trash, so the confirmation dialog had been read and accepted —
"This action cannot be undone. All survey data including sessions and answers will be
permanently deleted." Everything the UI promised then failed to happen, with no message
that says why.

The exception text names `SurveyMapLayer.survey`, which is misleading: that FK is `CASCADE`.
What actually protects is `Question.layer` → `SurveyMapLayer` with `on_delete=PROTECT`
(the same PROTECT that makes the Reference layers card refuse to delete a bound layer and
name the question). Django walks `SurveyHeader` → `SurveyMapLayer` by cascade, finds a
`Question` pointing at that layer, and refuses — even though the question is itself going
under in the same cascade, because PROTECT is evaluated while the collector is still
gathering rows, before anything is deleted. The exception's protected object is
`<Question: D Routen Mapsurvey>`, a `layer_objects` question in the very survey being
purged.

`purge_survey()` already has exactly this workaround for the other PROTECT in its path —
`SurveySession.survey` — with the comment "Sessions first (PROTECT FK prevents cascade
deletion)". Layers were never added when `layer_objects` landed.

This is not one stuck creator. In production today **9 of the 19 trashed surveys own
layers**, so nine Delete-forever buttons are dead. Worse, `purge_expired_surveys()` runs
the same `purge_survey()` in a bare loop, so the first such survey to pass its 30-day
retention window will raise and abandon every survey behind it in the same run — silently,
since the scheduler only sees a failed HTTP call. Retention is a promise on `/trust/`:
"deleted items are permanently purged by a scheduled job."

Now, because the 30-day windows of the surveys trashed during the September layer work are
about to open, and because a purge that half-runs leaves respondent answers on disk past
the retention we publish.

## What Changes

- `purge_survey()` deletes a survey's reference layers explicitly, in an order that clears
  the `Question.layer` PROTECT first, the same way it already handles sessions.
- Layer object attachments (`LayerObjectAsset`) are removed from storage before the DB
  rows go, matching the existing cover-image and question-image cleanup. There are zero
  such rows in production today, so this is written for the next purge, not this one.
- `purge_expired_surveys()` isolates a failing survey: one bad row no longer costs every
  survey behind it in the run. The failure is recorded rather than swallowed.
- The Delete-forever dialog names what else is going: "N reference layers with M objects".
  A creator who uploaded a 4,000-object layer should see that before the last confirmation,
  not after.

## Impact

- Affected specs: `survey-trash`
- Affected code: `survey/trash.py`, `survey/templates/editor.html`, `survey/views.py`
  (context for the dialog)
- No migration. No kill switch — rollback is a revert.
- Nothing about `Question.layer`'s PROTECT changes: refusing to delete a *layer* that a
  question is bound to is the correct behaviour on the Reference layers card and stays.
  This change is only about the survey-wide purge, where the question is going too.
