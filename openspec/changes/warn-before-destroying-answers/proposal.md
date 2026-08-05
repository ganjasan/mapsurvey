## Why

Deleting a question deletes every answer to it. `Answer.question` is `on_delete=models.CASCADE`
(`models.py:616`), and `editor_question_delete` calls `question.delete()` with no check
(`editor_views.py:522-530`). The only thing standing in the way is an `hx-confirm` reading
"Delete question 'X'?" — which says nothing about responses, because it was written for a survey
that had none.

A user reported the symptom without recognising the cause: their export came back empty except for
the last session, and they guessed their data was "older" than some change we had made. They were
right that the data was gone and wrong about why — they had edited the survey between test runs.

The exposure is narrower than it first looks, and worth stating precisely because it decides how
much machinery this deserves. **Versioning already protects published surveys.** `publish_draft`
does not delete the old structure: it creates an archived `SurveyHeader` and *moves* the previous
sections and sessions onto it (`versioning.py:236-260`), so the old version's questions stay live
rows and their answers stay attached. Production confirms it — 61 archived headers currently hold
1060 questions and 3466 answers. Published and closed surveys are further protected by the
read-only lock on structural edits.

What is unprotected is every survey that has never been published: **50 surveys in `draft` holding
842 answers and 12 in `testing` holding 1471**. There is no archived version to move anything to,
so deletion is final. That is exactly the state people are in while collecting their first
responses, and exactly where the reporter was.

## What Changes

- Deleting a question, sub-question or section that has answers requires an explicit confirmation
  naming how many answers will be destroyed. Without it the delete does not happen.
- The confirmation is enforced on the server, not only in the dialog, so the count cannot go stale
  between rendering the list and clicking, and the guard cannot be bypassed by a bare POST.
- The same confirmation explains that this survey is not versioned yet: once published, edits go
  through a draft copy and previous answers are preserved as an archived version. This is the one
  moment the author is guaranteed to be paying attention to the subject.
- Section deletion counts answers across all its questions, including sub-questions.

Not in scope: soft-deleting questions or blocking deletion outright. Both need new state on
`Question`, a migration, and changes to export, analytics and the editor — disproportionate for
data that is unversioned precisely because its author has not yet published anything. The harm to
fix here is the silence, not the deletion.

Also not in scope: discarding a draft copy, which destroys answers collected against that draft via
its test token. That is what discarding means, and the existing dialog already says the changes
will be lost.

## Capabilities

### New Capabilities
- `destructive-edit-confirmation`: what the editor must establish before an edit destroys collected
  answers — which edits count, what the author is told, and where the guard is enforced.

### Modified Capabilities

None. `survey-editor` in `openspec/specs/` does not currently specify deletion behaviour, so there
is no existing requirement to amend.

## Impact

- `survey/editor_views.py` — `editor_question_delete`, `editor_section_delete`.
- `survey/templates/editor/partials/question_list_item.html`, `section_list_item.html` — the delete
  controls and their confirmation.
- `survey/models.py` — a helper for counting answers under a question or section, including
  sub-questions. No field change, no migration.
- Backlog #98 closed, and its description corrected: it currently says editing a survey destroys
  the answers already given, which overstates the case by leaving out that versioning protects
  published surveys.
