# fix-question-modal-error-retarget

## Why

PostHog replay `01a051a7-c0fc-7381-937c-3f08196de039` (2026-08-30, creator 407, Safari/de):
the creator opened "New question", ticked "Shown conditionally", pressed Create four
times and rage-clicked the error text "Pick a controlling question and at least one of
its answers." — which never went away. Root cause: every error re-render of
`question_form_modal.html` on a POST is returned with status 200 and therefore swapped by
HTMX into the **form's** target, which for the create form is
`hx-target="#questions-list" hx-swap="beforeend"`. The modal HTML (with the error alert)
is appended under the question list; the open modal keeps its state, so each further
Create appends another copy. For the edit form (`outerHTML` of the list item) and the
sub-question form (`outerHTML` of the parent item) the modal would *replace* a list
item instead. The creator never sees the error where they are looking and cannot get
out of the loop except by closing the modal.

Second cause, found while reproducing the owner's own screenshot ("Shown conditionally"
selected, no picker appears): `_visibility_block.html` is included both in the section
panel (`section_detail_form.html`) and in the question modal, each carrying
`id="fg-visibility"`. The block's script does `getElementById`, so when the section panel
is open it finds the *section's* block, sees it already bound, and returns — the modal's
radios have no handler, the "When the answer to / is any of" picker never unfolds, and the
creator physically cannot satisfy the validation. Both bugs together are the loop in the
replay.

## What Changes

- New helper `_render_question_modal(request, context)` in `survey/editor_views.py`
  renders `question_form_modal.html` and, on an HTMX request, sets
  `HX-Retarget: #questionModalBody` + `HX-Reswap: innerHTML` so any re-render lands in
  the modal body regardless of the form's own target. All renders of that template
  (create, edit, sub-question create; GET and POST-error paths) go through it.
- `_visibility_block.html`: block located by class (`.fg-visibility`,
  `.visibility-controls`), script binds every unbound instance, read-only flag passed as
  `data-read-only` instead of template interpolation inside the script.
- Test in `survey/tests.py`: create POST in conditional mode without ticked answers,
  sent with `HX-Request`, returns the modal with the error, carries the retarget
  headers, and creates no question.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `survey-editor`: question modal validation errors are shown in the modal.

## Impact

- `survey/editor_views.py`, `survey/templates/editor/partials/_visibility_block.html`,
  `survey/tests.py`. No migration.
- htmx 1.9.10 (already loaded) supports both response headers.
