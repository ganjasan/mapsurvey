## Context

`survey_detail.html` renders the Survey context bar in two branches:

- **read-only** (`is_read_only and not is_draft_copy`, ~line 26) — the survey is `published` or
  `closed`; shows a lock, an "edit a draft" action, and `Preview`.
- **editable** (`else`, ~line 53) — `draft`, `testing`, or a draft-copy; shows `Preview`, and a green
  publish button only when `status == 'draft'` (or `Publish Version`/`Discard` for a draft-copy).

The collection lifecycle (`draft → testing → published/open → closed → archived`) is otherwise driven
by the status chip `_publishing_widget.html` in the top navbar. The JS is already there and reusable:
`doTransition(status)` (draft→published, published↔closed, back-to-draft) and `showPublishConfirm()`
(testing→published, which opens the "clear test data?" modal → `doPublishFromTesting`).

So the primary action for every state already has a working handler; it is simply not surfaced in the
context bar for `testing`, `open`, or `closed`.

## Goals / Non-Goals

**Goals:**
- The Survey context bar always shows `Preview` + one primary action/state, in every status.
- Reuse the existing transition JS and modals — no new endpoints, no new confirmation flows.
- Keep the status chip as the home of the advanced lifecycle (versions, discovery, results page).

**Non-Goals:**
- No new lifecycle states or transitions.
- No change to permissions, views, models, or migrations.
- Not moving the advanced controls out of the chip (that was the rejected "full inline parity"
  option — it would hide the chip and touch the sensitive publish logic).
- Draft-copy actions (`Publish Version`/`Discard`) unchanged.

## Decisions

### 1. A single state-driven "primary action" slot, reused across both branches

Introduce one include, `editor/partials/_survey_primary_action.html`, that renders the right-aligned
primary control from `survey.status` (owner only; no-op otherwise). Both the read-only and the
editable context-bar branches drop it into their right-hand action zone, so `open`/`closed`
(read-only) get the state+action too, not just `draft`/`testing`.

- `draft` → green **Publish** → `doTransition('published')` (matches today's button exactly)
- `testing` → green **Publish — open for responses** → `showPublishConfirm()` (the existing modal)
- `published` → **● Open** pill + outline **Close** → `doTransition('closed')`
- `closed` → **○ Closed** pill + outline **Reopen** → `doTransition('published')`

*Alternative considered*: a dropdown "Live · Open ▾" holding Close. Rejected — a second dropdown next
to the status chip duplicates the chip's job; an inline pill + one button is more legible and is what
the Public results bar does (state + one action).

### 2. Keep it presentation-only

The include reads `survey.status` and calls existing JS. Nothing server-side changes. The draft-copy
case (`show_draft_actions`) keeps its own `Publish Version`/`Discard` buttons and does not use the new
slot — a draft-copy's "primary action" is publishing the *version*, which is a different transition
with its own compatibility-check modal.

### 3. Guard by role, mirror the chip

The chip renders lifecycle controls only for `effective_role == 'owner'` and non-archived surveys.
The primary-action slot uses the same guard, so a viewer/editor sees only `Preview` (as today).

## Risks / Trade-offs

- **Two publish entry points now exist for `testing`/`open`/`closed`** (the chip and the context bar)
  → intentional and consistent (the chip is the advanced home; the bar is the primary action). Both
  call the same JS, so they cannot diverge.
- **The read-only branch gets busier** (edit-a-draft actions + Open/Close state) → mitigated by
  putting the collection state on the far right as its own group, visually separate from the
  versioning actions, matching the existing right-aligned layout.
- **A creator could Close a live survey from a more prominent button** → `doTransition('closed')` is
  reversible (Reopen), non-destructive to responses, and already one click away in the chip; making
  it visible is the point.

## Migration Plan

Template-only. Deploy is a plain merge. Rollback is a git revert; nothing persists state.

## Open Questions

- Should `open` also expose "Back to Draft" inline when nothing has been collected
  (`show_back_to_draft`)? Leaning no — that is an advanced, rare action and belongs in the chip; the
  bar stays focused on the one primary action per state.
