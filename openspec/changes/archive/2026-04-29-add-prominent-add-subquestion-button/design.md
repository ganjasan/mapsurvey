## Context

The WYSIWYG editor's question card (`survey/templates/editor/partials/question_list_item.html`) currently exposes the "create sub-question" affordance as one of three icon buttons in a `.q-actions` strip on the right side of the card row (alongside edit and delete). The icon used is `fa-sitemap`, which has no caption and does not visually distinguish itself from the other admin actions. Sub-questions are then listed under the parent in a `<ul class="subquestion-list">` that is rendered only when at least one sub-question exists — so a user who has never opened that menu has no visible cue that nesting is even possible.

Top-level question creation, by contrast, uses a prominent full-width dashed-border button (`.add-question-btn`) below the question list, with a `fa-plus` icon and an explicit "+ New Question" label. The asymmetry is the discoverability problem.

## Goals / Non-Goals

**Goals:**
- Move the sub-question entry point from the q-actions row to a prominent, always-visible button below the (possibly empty) sub-question list, only on geo-type question cards.
- Reuse the existing `.add-question-btn` look so editor users immediately recognise it as "the add affordance, scoped to this card".
- Keep the existing read-only state semantics (button disabled with "Create a draft to edit" tooltip when survey is published or closed).
- Keep parity with the icon button's gating: only point/line/polygon questions get the affordance.

**Non-Goals:**
- No backend changes — `editor_subquestion_create` already returns the parent question partial via HX-Trigger, and the modal form template (`question_form_modal.html`) already branches on `parent` for the POST URL.
- No drag-and-drop of sub-questions across geo-question parents (out of scope, tracked separately).
- No paste-as-subquestion functionality (tracked in #16).
- No onboarding hints, tooltips beyond the existing read-only one, or empty-state copy ("No sub-questions yet"). Discoverability comes from the button's prominence alone in this change.

## Decisions

### Decision 1: Button styling — reuse `.add-question-btn` with a `--sub` modifier

The base `.add-question-btn` is sized for a section-level "+ New Question" affordance: `padding: 0.75rem`, `font-size: 0.9rem`, `border: 2px dashed`. Dropping that style verbatim inside a question card looks chunky relative to the card itself. We therefore add a small modifier class `.add-question-btn--sub` that reduces padding (`0.5rem 0.75rem`) and font-size (`0.8rem`) for the nested context, while preserving the dashed border, full-width layout, `fa-plus` icon, and disabled-state visuals.

**Alternative considered:** ship a new `.add-subquestion-btn` class with separate styling. **Rejected** because it duplicates the dashed-border / hover-accent / disabled rules and weakens the visual relationship the change is trying to establish ("this is the same kind of button, scoped to this card").

### Decision 2: Wrapper element to handle "above" vs "between" placement

The button needs to sit below the (optional) `<ul class="subquestion-list">`. When the list is non-empty, the list itself already provides a top dashed separator; when empty, the button is a direct sibling of `.question-item-row` and needs its own visual transition. We wrap the button in a `<div class="add-subquestion-wrap">` and rely on the CSS sibling selector `.question-item-row + .add-subquestion-wrap` to apply a dashed top border only in the empty case. This keeps the template free of conditional separator classes.

**Alternative considered:** always render a non-empty `<ul class="subquestion-list">` even with no children, and put the button inside. **Rejected** because it introduces an empty `<ul>` which carries semantic and accessibility implications.

### Decision 3: Gate by `input_type` only, not by nesting depth

The template includes itself recursively for sub-questions (`{% include "editor/partials/question_list_item.html" with question=subq %}`). Sub-questions are never geo-typed — the product intentionally does not allow point/line/polygon as a sub-question type, and the form layer (Decision 4) now enforces that constraint — so the recursive include never reaches a card that would re-render the new button. We therefore gate the button on `input_type in (point, line, polygon)` alone, without an extra "is top-level" check. This keeps the template branching minimal and matches the gate the old `fa-sitemap` button used.

### Decision 4: Enforce the "no geo sub-questions" rule in `QuestionForm`, not in the view

Until now the rule "a sub-question cannot itself be a geo question" lived only in product convention — neither the form nor the view rejected `input_type=point` on a sub-question POST. The new prominent entry point makes the create flow much more visible, so the rule needs an explicit enforcement layer.

We chose `QuestionForm` as that layer: the form gains an `is_subquestion: bool` keyword argument; when true, the `input_type` field's `choices` are filtered to exclude the constants in `SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')`. Django's built-in choice validation then rejects any POST that submits a filtered value, with the standard "Select a valid choice" error. The view layer wires the kwarg from the two callsites where sub-question context is known: `editor_subquestion_create` (always `True`) and `editor_question_edit` (passes `bool(question.parent_question_id_id)`).

**Alternatives considered:**
- *Reject in the view with an explicit 400.* Rejected — duplicates Django's choice validation and forces a custom error path that the modal would not render naturally.
- *Filter the choices in the template only.* Rejected — UI-only enforcement is bypassable by any crafted POST and would silently allow inconsistent data through.
- *Add a model-level `clean()` constraint.* Rejected for this change — the rule is editor-flow-specific, the model is shared with imports / admin / fixtures where applying the same constraint could break legitimate paths. If we later decide the rule must hold at the data layer, the form's constant becomes the single source of truth and a model `clean()` can call into it.

## Risks / Trade-offs

- **Vertical space** → Always rendering an "Add Sub-question" button on every geo question card adds ~36px of vertical space per card, even on cards the user has no intention of nesting. **Mitigation:** the smaller `--sub` modifier keeps the addition compact; the visible affordance is the explicit goal.
- **Visual noise on surveys with many geo questions** → A large section with five point-type questions now shows five "+ Add Sub-question" buttons. **Mitigation:** matches the existing pattern at the section level (one "+ New Question" per section) so the visual idiom is consistent. We accept this as the cost of discoverability.
- **HTMX preview iframe refresh** → The new button uses the same `hx-target="#questionModalBody"` + modal form pattern as the icon button, so the existing `htmx:afterSettle` listener already re-initialises Sortable on `.subquestion-list` and the iframe refresh continues to work without changes.

## Migration Plan

Single-step deploy: ship the template + CSS change. No data migration, no URL changes, no feature flag needed. Any user mid-session with the old template will pick up the new one on next page load.

## Open Questions

None — the issue (#17) fully specifies placement, style, scope, removal, and read-only behaviour.
