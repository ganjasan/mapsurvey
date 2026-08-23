# Design: choice-dropdown-display

## Context

`choice` questions render exclusively as `forms.RadioSelect` (`forms.py:274`). The
`display_style` machinery (model field, editor picker, `resolve_display_style`,
serialization round-trip) already exists but is scoped to rating questions:
`resolve_display_style` whitelists `CHOICE_BASED_STYLES` (scale_strip/list_pips/stars) and
the import whitelists `('default', 'scale_strip', 'list_pips')`. The live trigger is the
Olney demo: a 35-option zone question renders as 35 radios and pushes the geo questions
below the fold on a phone — the primary device of that survey's audience.

Constraint: merge reaches prod in minutes with no staging; the change must not alter any
existing survey's rendering unless a creator opts in.

## Goals / Non-Goals

**Goals**
- Respondent-side searchable dropdown rendering for `choice` questions that opt in via
  `display_style = "dropdown"`.
- Editor affordance to pick the style on choice questions.
- `dropdown` survives export→import.

**Non-Goals**
- No auto-switch by option count (silent behavior change to existing surveys; can be a
  follow-up as an editor *suggestion*, never a runtime default).
- No `multichoice` support in this change (checkbox semantics + search is a separate UX
  problem; the plumbing added here does not preclude it).
- No new JS dependency (no select2/tom-select); vanilla filter only.
- No changes to how choices are stored (`choices` JSON is untouched).

## Decisions

1. **Custom widget over native `<select>` / `<datalist>`.** Native `<select>` has no search
   box; `<datalist>` behaves inconsistently across mobile browsers and validates free text.
   The widget renders a read-only-styled search `<input>` plus a hidden `<select>` (the
   real form field, keeps Django `ChoiceField` validation untouched) and a filterable
   option list `<ul>`. JS: type → filter items (case-insensitive substring on label);
   tap/Enter → set the hidden select's value, show the label in the input, close the list.
   The submitted value stays the choice `code`, exactly as RadioSelect submits today.
2. **Style resolution.** `_get_form_from_input_type` branches on
   `input_type == 'choice' and display_style == 'dropdown'`. `resolve_display_style` gains
   a per-input-type map instead of the rating-only whitelist: `{'rating': {...existing},
   'choice': {'dropdown'}}`. Any other stored value on a choice question keeps rendering
   radios — same fallback philosophy as rating.
3. **Editor.** Reuse the existing display-style select in the question modal, shown for
   `choice` with options List (default) / Dropdown with search. Server-side save path
   already persists `display_style`; extend its validation to accept `dropdown` only when
   `input_type == 'choice'`.
4. **Serialization.** `_create_question` whitelist becomes type-aware the same way; an
   archive with `display_style: "dropdown"` on a non-choice question falls back to
   `default` (existing unknown-value rule).
5. **Kill switch not needed.** Opt-in per question means the blast radius of a rendering
   bug is exactly the questions whose creators chose the style; radio rendering is
   untouched code.

## Risks / Trade-offs

- **Mobile keyboard vs map layout**: focusing the search input opens the keyboard over the
  panel; acceptable because the panel (not the map) hosts the field, but test on a real
  phone.
- **`question_form_modal.html` collision** with the in-flight `formatted-text-wysiwyg`
  change (same file modified in the working tree). Coordinate merge order; keep this
  change's edits minimal and localized to the display-style block.
- **Accessibility**: filterable listbox needs `role="listbox"`/`aria-expanded` and
  arrow-key navigation; keep to the minimal correct set rather than a full combobox spec.

## Migration Plan

One state-only migration (`0053_choice_dropdown_display_style`): `dropdown` joins
`DISPLAY_STYLE_CHOICES`, which changes no DB schema but is required because
`ModelForm._post_clean` runs `full_clean` against the model's `choices` — keeping the
value out of the model (the original plan) makes the editor form reject it at the model
validation layer. **Numbering conflict**: the in-flight `formatted-text-wysiwyg` change
also carries an uncommitted `0053_*` migration off `0052`; whichever merges second must
renumber ([[feedback-parallel-migration-conflicts]]). After deploy, set the style on the
Olney zone question (id 4190) via one UPDATE. Rollback = revert the deploy; stored
`dropdown` values then hit the unknown-value fallback and render as radios — degraded
but functional.

## Open Questions

- Threshold hint in the editor ("this question has 10+ options — consider dropdown"):
  worth a follow-up backlog item, out of scope here.
