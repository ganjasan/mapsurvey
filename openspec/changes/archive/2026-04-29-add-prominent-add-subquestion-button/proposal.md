## Why

In the WYSIWYG survey editor, the entry point for adding sub-questions to geo questions (point/line/polygon) is a small `fa-sitemap` icon tucked into the q-actions row of each question card. The icon reads as a generic "tree" affordance, has no label, and is structurally inconsistent with how top-level questions are added (the prominent "+ New Question" button below the section list). Power users have used the feature heavily (one user has 34 sub-questions), but only ~4 of ~50 active editor users have ever discovered it — the discoverability gap is substantial enough to be tracked as a backlog item (`openspec/backlog/idea-subquestion-discoverability-testing.md`).

## What Changes

- Add a "+ Add Sub-question" button **inside** every geo-question card (point/line/polygon), rendered below the sub-question list and always visible — even when the list is empty.
- Style the button to match the existing `add-question-btn` (full-width, dashed-border, subdued, `fa-plus` icon), with a small modifier to right-size it for the nested context.
- Wire the button to the existing `editor_subquestion_create` endpoint via the same HTMX modal pattern used by all editor question/edit affordances.
- Honour the existing read-only state: when the survey is published/closed, the button is `disabled` and shows the same "Create a draft to edit" tooltip as siblings.
- **REMOVED**: the `fa-sitemap` icon button in the q-actions row of geo-question cards. The new button replaces it as the single entry point — no two equivalent affordances for the same action.
- Restrict the `input_type` choices in `QuestionForm` to non-geo options (excluding `point`, `line`, `polygon`) when the form is used for sub-question creation or for editing an existing sub-question. This codifies an existing product rule (a sub-question cannot itself be a geo question) at the form layer, so the new prominent entry point cannot be used to create a malformed sub-question type.

## Capabilities

### New Capabilities
- _None._

### Modified Capabilities
- `survey-editor`: The `Sub-question management for geo questions` requirement changes its UI affordance — the entry point moves from an icon button in the q-actions row to a prominent, always-visible button rendered below the sub-question list. Behaviour (creating a sub-question with `parent_question_id` set to the geo question) and the gating rule (only on point/line/polygon) are unchanged.

## Impact

- Templates: `survey/templates/editor/partials/question_list_item.html` (move entry point), `survey/templates/editor/editor_base.html` (small CSS modifier for the nested button).
- Forms: `survey/editor_forms.py` — `QuestionForm` gains an `is_subquestion` kwarg that filters geo input types out of the `input_type` field's choices (constant `SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')`).
- Views: `survey/editor_views.py` — `editor_subquestion_create` instantiates `QuestionForm(is_subquestion=True)`; `editor_question_edit` instantiates `QuestionForm(is_subquestion=bool(question.parent_question_id_id))` so the same restriction applies when editing an existing sub-question.
- Tests: extend `EditorSubquestionTest` in `survey/tests.py` to cover the new button (visible/absent/disabled, sitemap removed) and the input-type filter (form excludes geo on create+edit, server rejects geo POSTs, top-level edit still allows geo).
- Backwards compatibility: existing sub-questions are unaffected (no data migration). Top-level question creation/edit is unchanged. The icon-button is removed in the same change. No URL or API surface changes.
