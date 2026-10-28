# Design — fix-question-modal-error-retarget

## Context

The question modal is loaded into `#questionModalBody` by HTMX (GET). The `<form>` inside
carries a target for the *success* response (a rendered `question_list_item.html`):
`#questions-list beforeend` for create, the item's `outerHTML` for edit/sub-question. The
server reuses the same `render(...)` call for validation failures, returning the modal
template with status 200 — HTMX cannot tell the two apart and swaps the modal into the
list.

## Decision

Server-side retarget via response headers rather than a client-side `htmx:beforeSwap`
hook or a 422 status:

- `HX-Retarget` / `HX-Reswap` are the HTMX-native way to say "this response goes
  elsewhere"; they need no JS on the page and work for all three forms at once.
- A 4xx status would make HTMX drop the swap entirely (it ignores error responses by
  default), so the error would still be invisible without extra JS. The autosave path
  already uses 422 JSON deliberately for its own indicator; that stays as is.
- One helper instead of touching nine `render` calls individually, so a future render
  cannot forget the headers. GET renders also pass through it — the headers are a no-op
  there (target is already `#questionModalBody`).

## Out of scope

Why the creator ticked no answer in the first place (the answer checkboxes sit at the
bottom of a long modal). Worth a follow-up UX look; the loop itself is the bug.
