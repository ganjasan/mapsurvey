## Why

A closed survey cannot be edited and the editor offers no way out of that state.

The read-only lock itself is right: a survey with live responses must not be edited in place, and
versioning provides the correct route via a draft copy. The problem is that the route is only
advertised, and only permitted, for `published`. `show_edit_published` requires
`survey.status == 'published'` (`editor_views.py:146-148`) and `editor_create_draft` rejects
anything else outright (`editor_views.py:1166-1167`). So on a **closed** survey the read-only banner
renders with no action at all: no "Create a draft copy", no "Go to draft", and a status dropdown
offering only Reopen and Archive.

The actual sequence — Reopen, *then* create a draft copy — is not discoverable, and reopening a
survey you deliberately closed looks wrong enough that a careful person will not try it. **5 of the
7 closed surveys in production have no draft copy**, so they are in this state now.

The user who reported it took the only path he could see: "I clicked on the publish-Button to see
what happened. After that, i can't go back. So I closed the survey... I fixed that with a work-around:
I make a copy to new one." That workaround costs him the responses and the survey URL.

His path also exposes a second gap. He published to see what would happen, on a survey nobody had
answered. There is no cheap undo for that: `published → draft` is not a valid transition at all, so
an accidental publish is permanent even when nothing has been collected. **3 published surveys in
production have zero sessions.**

## What Changes

- A closed survey offers the same "Create a draft copy" route a published one does, in the banner
  and in the endpoint behind it.
- Publishing that draft leaves the canonical survey closed. Editing a survey and reopening it to
  respondents stay two separate decisions; publishing a new version SHALL NOT silently start
  accepting responses again.
- `published → draft` and `closed → draft` become valid **only** while the survey has never
  collected anything — no sessions of its own and no archived versions. That covers the
  publish-by-accident case directly and needs no draft copy.
- The read-only banner names the next action instead of only stating the lock.

Not in scope: letting a survey with responses return to `draft`. That is what versioning is for, and
allowing it would put the answer-destroying edits that #98 just guarded back on the table by another
route.

## Capabilities

### New Capabilities
- `survey-edit-recovery`: how an author gets back to editing from a state where editing is locked —
  which lifecycle transitions are permitted when, when a draft copy may be created, and what the
  editor tells them.

### Modified Capabilities

None. `survey-editor` in `openspec/specs/` does not specify the lifecycle or the read-only banner,
so there is no existing requirement to amend.

## Impact

- `survey/models.py` — `VALID_TRANSITIONS` and `can_transition_to`, plus a helper for "has never
  collected anything".
- `survey/editor_views.py` — `editor_create_draft`, `show_edit_published`.
- `survey/templates/editor/survey_detail.html` — the read-only banner and the status dropdown.
- No migration; this is lifecycle rules and template gating over existing fields.
- Backlog #100 closed. Answers the reporter's sixth point, and makes his copy-the-survey workaround
  unnecessary.
