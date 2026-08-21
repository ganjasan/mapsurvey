# Leaked modal backdrops stack up and make the editor unclickable

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-08-17

## Description

Bootstrap modal backdrops leak in the survey editor. Observed in production on 2026-08-17
with the first real AI-draft user (user 371): PostHog dead-click events on
`/editor/surveys/<uuid>/` carry the element chain

```
div.fade.modal-backdrop … nth-of-type="9"
```

— **nine** orphaned `.modal-backdrop` elements stacked in `<body>`. Each has `fade` without
`show`, so it is fully transparent but still intercepts every click on the page. The user
clicked the editor 8 times in three minutes (17:33–17:36 UTC), hit the invisible overlay,
got nothing, and recovered only by navigating away and back (visible as `$pageview` bursts
right after each dead-click series).

## Suspected mechanism

Editor modals (`#questionModal`, `#mapPickerModal`, publish modals in
`partials/_lifecycle_scripts.html`) are opened via Bootstrap `data-toggle` while HTMX swaps
their content into `#questionModalBody`. If the modal's DOM (or content the plugin holds a
reference to) is replaced by an HTMX swap while the show/hide transition is still running,
jQuery's modal plugin loses track and never removes its backdrop. Every subsequent open adds
another one.

## Why it matters

- Blocks the whole editor, not just the AI path — any author who opens enough modals in one
  session ends up with an unclickable page and no error anywhere.
- Direct product damage observed: user 371 apparently tried to open a multichoice question
  for editing right before publishing (dead click on the "Multiple Choices" badge at
  17:34:56), could not, and published the AI draft as-is. Earlier the same session, the same
  user abandoned a draft copy (survey 458) after 3 minutes of dead clicks and **regenerated
  the survey from scratch instead of editing** — regeneration was cheaper than repair, which
  means an AI failure would have lost the user entirely.

## Fix sketch

- Before every `modal('show')`, remove orphaned `.modal-backdrop` elements that have no
  visible modal (`$('.modal.show').length === 0`).
- Never HTMX-swap a modal's DOM while it `hasClass('show')` — defer the swap to
  `hidden.bs.modal`, or swap only the inner body that Bootstrap holds no reference to.
- A cheap belt-and-braces guard: on `hidden.bs.modal`, `$('.modal-backdrop').not(':first')…`
  cleanup, or cap backdrops to one.

## Reproduction

Open/close editor modals repeatedly while HTMX requests are in flight (slow network helps);
count `document.querySelectorAll('.modal-backdrop').length`.
