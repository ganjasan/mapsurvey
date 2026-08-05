## Context

Deletion in the editor is an HTMX post from a trash button, guarded by `hx-confirm` — a static
string rendered into the markup. The server side does no checking beyond permissions and the
read-only lock (`_check_structural_edit_allowed`, which returns 403 for `published` and `closed`).

The cascade runs `SurveySection` → `Question` → `Answer`, and separately `Question` →
sub-`Question` → `Answer` via `parent_question_id`. So a section delete can destroy answers to
questions the author is not looking at, and a question delete can destroy answers to its
sub-questions.

Prior art worth matching: publishing a draft already works as check-then-confirm. `checkAndPublishDraft()`
calls `editor_check_compatibility`, and if issues come back it opens a modal listing them before
`doPublishDraft(force)` re-posts with an explicit override. The same shape fits here, and reusing it
keeps one vocabulary for "this is destructive, here is what it costs, confirm".

Constraint that shapes the design: a count rendered into the page at list-render time is stale the
moment another respondent submits. For a warning whose entire job is to state a number truthfully,
that matters.

## Goals / Non-Goals

**Goals:**

- No edit destroys answers without the author being told how many, in that moment.
- The guard holds on the server, so it cannot be bypassed and the number cannot be stale.
- The author learns, at the moment it is relevant, that publishing changes this — that versioning
  preserves previous answers.
- Section deletion accounts for every answer beneath it, sub-questions included.

**Non-Goals:**

- Soft-delete or blocking deletion (see proposal). The decision was taken deliberately: the data at
  risk belongs to surveys nobody has published, and the reported harm is silence rather than the
  deletion itself.
- Changing the cascade. `on_delete=CASCADE` stays; a delete that the author confirms should still
  delete.
- Anything about discarding a draft copy.
- Undo. Worth wanting, but it is a different feature with its own storage question.

## Decisions

### D1 — Enforce the confirmation server-side, with the count computed at request time

The delete endpoints refuse a delete that would destroy answers unless the request carries an
explicit acknowledgement. On refusal they return the count so the client can ask. The count is read
inside the same request that performs the delete.

*Why not just a better `hx-confirm` string:* the string is baked in when the list renders. On a
survey that is actively collecting, "this will delete 3 answers" can be wrong by the time it is
read, and a bare POST skips it entirely. A warning that is sometimes wrong about the number is
worse than no number, because it teaches the author to disbelieve it.

*Shape:* `POST` without acknowledgement and with answers present → `409` plus the count as JSON.
With `confirm_delete_answers=true` → proceed. Chosen over a two-endpoint check-then-delete because
one endpoint cannot drift out of step with itself, and the count returned is the count the delete
would have destroyed.

### D2 — One counting helper, used by both endpoints and both templates

Add a helper that answers "how many answers hang beneath this question" (its own plus its
sub-questions') and one for a section (all its questions, sub-questions included). Both endpoints
and the confirmation text read from it.

*Why:* the section case is the one most likely to be got wrong by hand, since sub-question answers
are invisible in the section list. Writing the traversal once means the section dialog cannot
quietly undercount.

### D3 — Say what publishing would change, only when it would change something

The confirmation includes a sentence about versioning **only** for a survey that has never been
published (`version_number == 1` and no archived versions). For a draft copy of a published survey,
the sentence would be false — that author already has version protection, and their draft's answers
are test data by construction.

*Why here rather than a banner somewhere:* the author is, at this instant, being told they are about
to lose responses. That is the only moment when "publishing would have preserved these" is
information rather than noise. A permanent banner in the editor would be ignored within a day.

*Wording constraint:* it must not read as "publish now to be safe". Publishing a half-built survey
to protect two test answers is worse advice than losing them. It states what versioning does; it
does not recommend an action.

### D4 — Confirm on the count, not on the act

The dialog is shown when there is something to lose. Deleting a question with no answers keeps
today's plain `hx-confirm` and stays a single click.

*Why:* a confirmation that always fires is trained away. Reserving the interruption for the case
that actually costs something is what keeps it readable.

## Risks / Trade-offs

**A 409 for a business condition rather than an error** → It is a conflict in the ordinary sense —
the request cannot proceed in the state the resource is in — and HTMX handles a non-2xx cleanly with
`htmx:responseError`. The alternative, 200 plus a body meaning "not done", is the shape that gets
misread later as success.

**Two round trips to delete a question that has answers** → Only for deletes that would destroy
data, which should be rare and deserve the pause. Empty questions stay one click.

**The versioning sentence could be read as advice to publish early** → Mitigated by wording (D3) and
worth checking with a real author before it ships, since we cannot judge our own copy for this.

**Counting on every delete adds queries** → Two counts on a path invoked by hand, in an editor, by
one person. Not a hot path.

## Migration Plan

No schema change and no migration; the helper counts through existing relations. Nothing is
backfilled, and existing surveys behave identically until someone deletes something with answers
attached.

Rollback is a revert. No stored state depends on this.

## Open Questions

- Should the same guard cover *editing* a question in ways that invalidate stored answers — changing
  `input_type`, or removing choice codes that answers reference? `check_draft_compatibility` already
  detects exactly these for the published path, so the detection exists and only the unpublished
  path is unguarded. Left out here to keep the change to deletion, but it is the obvious next step
  and the same helper would serve.
- Is 409-plus-JSON the right shape for the rest of the editor's destructive actions, or is this
  change inventing a local convention? Worth a look at how survey deletion and draft discard
  currently confirm before this spreads.
