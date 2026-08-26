# Tasks

## 1. Server: structured errors from the invalid branch

- [ ] 1.1 In `_start_survey_generation` (survey/editor_views.py), build a per-field error
      structure: list of `{field_id, label, messages}` using each form field's
      `auto_id`, keeping the flat label-prefixed list as fallback for unanchored
      rendering. Pass both to `generation_invalid.html`.
- [ ] 1.2 Update `partials/generation_invalid.html`: embed the per-field errors as a
      `<script type="application/json" data-gen-field-errors>` payload; keep the card
      markup but render it only for messages without field anchors (and for the
      not-configured path, which is a separate template context with no `field_errors`).

## 2. Client: distribute errors to their source

- [ ] 2.1 In `survey_create.html`, add a shared helper `markFieldErrors(errors)`:
      red border on the input, `.field-error` message div inserted after it,
      `details.ai-more` forced open when the field sits inside it, first field
      scrolled into view + focused; `clearFieldErrors()` removes all marks; an
      `input` listener on a marked field clears its own mark.
- [ ] 2.2 Hook HTMX: on `htmx:beforeRequest` of `#generate-btn` call
      `clearFieldErrors()`; on `htmx:afterSwap` of `#generation-slot` read the JSON
      payload (if present) and call `markFieldErrors`.
- [ ] 2.3 Replace the bare `goal.style.borderColor = '#dc2626'` in
      `wizardNext('draft')` with the same helper (message "This field is required.",
      clear-on-input included).

## 3. Mobile wizard copy

- [ ] 3.1 Change the `wizard-draft-next` button label from "✨ Draft my survey" to
      "✨ Next — choose the place" (survey_create.html). Leave `#generate-btn`'s
      desktop/mobile labels and the map-step "✨ Create draft survey" untouched.

## 4. Tests

- [ ] 4.1 Test: invalid generate POST (empty goal) returns the fragment with a JSON
      payload whose `field_id` equals the brief form's `goal` auto_id, and no visible
      error card list for anchored errors (GIVEN/WHEN/THEN docstrings).
- [ ] 4.2 Test: not-configured path still renders the plain card (no payload, no crash).
- [ ] 4.3 Update the existing assertion at survey/tests.py:25543 if the banner copy
      moves; test the wizard button copy renders "✨ Next — choose the place".
- [ ] 4.4 Run the template-comment guard test after template edits, then the relevant
      test classes once (baseline → after), no linter loops.
