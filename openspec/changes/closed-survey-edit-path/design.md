## Context

The lifecycle is `draft → testing → published → closed → archived`, with `testing → draft` the only
backward step (`models.py:83-89`). Structural edits are blocked for `published` and `closed`
(`_check_structural_edit_allowed`), and versioning supplies the sanctioned way to change a live
survey: clone a draft copy, edit that, publish it as a new version while the previous structure and
its sessions move onto an archived header.

All of that is sound. What is missing is that the machinery is gated on `published` in two places
that did not need to be — the template flag and the endpoint — leaving `closed` with the lock and
none of the remedy.

Two distinct situations get conflated in the reports, and separating them decides the design:

- **A survey with responses that is closed.** The author wants to change it. Versioning already
  answers this; only the gate is wrong.
- **A survey published by accident, with nothing collected.** Versioning is a heavy answer to this —
  a draft copy, a new version number, an archived header for a version nobody answered. What the
  author wants is to undo the publish.

## Goals / Non-Goals

**Goals:**

- A closed survey has a visible, permitted route back to editing.
- An accidental publish is reversible while nothing has been collected.
- Editing a survey and reopening it to respondents remain separate decisions.
- The read-only banner names the next action rather than only stating the lock.

**Non-Goals:**

- Returning a survey with responses to `draft`. Versioning exists precisely so that does not have to
  happen, and permitting it would re-open the answer-destroying edits that the delete guard now
  covers.
- Editing published or closed surveys in place. The read-only lock stays exactly as it is.
- Changing what `publish_draft` does to sections and sessions.
- Reworking the status dropdown beyond the entries these rules add.

## Decisions

### D1 — Allow a draft copy from `closed`, not just `published`

Both the template flag and `editor_create_draft` accept `closed` as well. Nothing else changes:
`clone_survey_for_draft` copies structure and never reads the canonical's status, and `publish_draft`
moves sections and sessions regardless of it.

*Why not instead teach the author to Reopen first:* that is the existing path, and it requires
reopening a survey to respondents purely to gain access to the editor. It makes the author take a
public-facing action to achieve a private one, which is why nobody finds it.

### D2 — Publishing a draft of a closed survey leaves it closed

`publish_draft` does not currently touch the canonical's status, so this falls out for free. It is
recorded as a decision rather than an accident because the alternative is tempting and wrong:
"publish version" reading as "reopen to the public" would silently start collecting responses on a
survey the author had deliberately closed.

*Consequence to handle in the UI:* after publishing, the author is looking at a closed survey with
their changes in place. The status dropdown already offers Reopen, so the second decision is one
click away and is theirs to make.

### D3 — Un-publish only while nothing has been collected

Add `draft` to the valid transitions from `published` and `closed`, gated in `can_transition_to` on
the survey having no sessions of its own **and** no archived versions.

Both halves matter. Sessions alone would be satisfied by a survey that published v1, collected
answers, then published v2 — the sessions moved onto the archived header, so the canonical shows
zero while the survey plainly has history. Requiring `version_number == 1` and no archived versions
closes that.

*Why put a data condition inside `can_transition_to`:* it already carries conditions of this kind
(`testing` and `published` require structure and a head section), so this is the established place
for them rather than a new concept.

*Why not a separate "unpublish" endpoint:* a transition is what this is, and the existing dropdown
already drives transitions. A second mechanism for the same state change would be one more thing to
keep consistent.

### D4 — The banner names the action

The read-only banner currently states the lock and, on published surveys, sometimes offers a button.
It should always end in something the author can do: go to the existing draft, create one, or — when
the survey has collected nothing — return it to draft.

*Why this is part of the change rather than polish:* the reported failure was not that the action was
forbidden, it was that the author could not see one. Fixing the permission without fixing the
affordance would leave the bug reproducible for anyone who does not already know the answer.

## Risks / Trade-offs

**"Back to draft" on a published survey could be read as a safe undo in general** → It is only
offered while nothing has been collected, which is exactly when it is safe. The risk is that an
author sees it once and expects it later; mitigated by it simply not being there once a response
arrives, rather than being there and failing.

**Un-publishing breaks the public URL for anyone holding it** → That is what un-publishing means, and
it is reversible by publishing again. It only applies to surveys nobody has answered, so nobody is
mid-response when it happens.

**Publishing a draft of a closed survey produces a new version that is not accepting responses** →
Intended (D2), but potentially surprising. The status is visible in the header the whole time, and
Reopen is adjacent.

**A draft copy of a closed survey is a state that did not exist before** → It goes through the same
`publish_draft` path as any other draft; the compatibility check and the archived-version mechanics
do not read the canonical's status. Worth a test that asserts exactly that rather than trusting the
reading.

## Migration Plan

No schema change and no migration. The rules are evaluated at request time, so the 5 closed surveys
currently without an edit path gain one the moment this deploys, with no backfill.

Rollback is a revert. Draft copies created from closed surveys in the meantime remain valid — they
are ordinary drafts, and publishing them would still work.

## Open Questions

- Should `archived` get the same treatment? It is currently terminal, with no transitions out at all.
  Nobody has reported it, and archiving is a deliberate end-of-life action rather than something you
  click to see what happens, so it is left alone here.
- When an author un-publishes to `draft`, should the test token be regenerated so previously shared
  links stop working? Arguably yes for a survey being taken back into development, but it is a
  separate decision about link hygiene and no one has asked for it.
