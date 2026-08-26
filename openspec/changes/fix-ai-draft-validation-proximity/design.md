## Context

The generate action on `/editor/surveys/create/` is an HTMX button (`#generate-btn`,
`hx-target="#generation-slot"`). On validation failure `_start_survey_generation`
(survey/editor_views.py) flattens `form.errors` + `brief_form.errors` into label-prefixed
strings and renders `partials/generation_invalid.html` into `#generation-slot` — a banner
at the bottom of the left column, far from the empty goal textarea. The field itself is
untouched. By contrast the mobile wizard's `wizardNext('draft')` already refuses to
advance with an empty goal and paints the border red — but shows no message and never
clears the highlight.

Only `goal` is required in `SurveyBriefForm` (`use_required_attribute = False`, so the
browser never intervenes — deliberate: the brief shares one `<form>` with "Create empty").
`SurveyCreateForm.name` can also error (max_length), and audience/map_target have
max_lengths, so the mechanism must be per-field generic, not goal-only.

Mobile wizard copy: step-1 primary button "✨ Draft my survey" advances to the map step;
the actual submit is the map-step "✨ Create draft survey" button. Step-1 copy implies
immediate creation.

## Goals / Non-Goals

**Goals:**
- Field-level, in-place presentation of generate-action validation errors on all
  viewports: red border + message directly under the offending input.
- First offending field scrolled into view and focused; errors inside the collapsed
  "Add details" disclosure force it open.
- Highlights clear on input and on the next generate attempt.
- Non-field failures (provider not configured) keep the existing `#generation-slot` card.
- Mobile wizard step-1 draft button copy signals a following step.

**Non-Goals:**
- No HTML5 `required` on brief fields (would break the shared "Create empty" submit —
  documented in `SurveyBriefForm`).
- No changes to the draft-content validation gate (`invalid_draft`) or the poller.
- No redesign of the wizard flow itself.

## Decisions

**D1 — Server stays the validator; the response carries structured errors.**
`_start_survey_generation`'s invalid branch returns per-field data (field id → messages)
instead of only flattened strings. Client-side-only validation would duplicate rules
(max_lengths) and drift. Rendering: keep returning a fragment to `#generation-slot`, but
the fragment now carries the errors as a JSON `<script type="application/json">` payload
(or data attributes) plus a visually hidden fallback list; a small JS handler on
`htmx:afterSwap` distributes them to the fields. Alternative considered — returning
HTML per field with `hx-swap-oob` — rejected: it would need an error slot pre-rendered
under every field and couples the partial to the page's DOM ids more tightly than a
single handler does.

**D2 — One shared JS helper for both paths.** The distribution logic (mark field, insert
`.field-error` div after it, open enclosing `<details>`, scroll+focus first) lives in
`survey_create.html` and is reused by `wizardNext('draft')`'s empty-goal check, replacing
the bare `borderColor` line — so mobile gains the message and the clearing behavior for
free.

**D3 — Clearing.** An `input` listener on a marked field removes its highlight and
message; every new generate attempt (htmx `beforeRequest` / wizard check) clears all
previous marks first. No timers.

**D4 — Banner demotion, not deletion.** `generation_invalid.html` keeps the card for
messages without a resolvable field anchor (provider not configured keeps its own
existing path; unknown-field errors fall back to the card). When every error is
anchored to a field, the slot renders nothing visible.

**D5 — Mobile copy.** Step-1 draft button becomes "✨ Next — choose the place" — the same
"Next — choose the place" vocabulary the non-AI footer button already uses, keeping the
sparkle to mark the AI path. The path identity stays visible because the ghost button
("Skip and start from scratch") names the alternative, and the map step's submit still
says "✨ Create draft survey".

## Risks / Trade-offs

- [JSON payload id mismatch after template refactors] → the fallback list in the card
  still shows the errors, so a broken anchor degrades to today's behavior, not silence;
  test asserts the payload's field ids match rendered inputs.
- [Focus/scroll fighting the wizard's step switcher on mobile] → the wizard path never
  goes through HTMX for the empty-goal case (it blocks before `wizardGoto('map')`), so
  the two entry points don't overlap.
- [Copy change weakens "draft" affordance on step 1] → mitigated by keeping ✨ and the
  tinted AI panel context; the button sits directly under the AI privacy note.

## Migration Plan

Template + view-branch change, no data, no flags needed; ships in one PR. Rollback =
revert. (`CREATE_STEER_AI` / `MOBILE_EDITOR_NAV` gating of surrounding markup is
untouched.)

## Open Questions

None.
