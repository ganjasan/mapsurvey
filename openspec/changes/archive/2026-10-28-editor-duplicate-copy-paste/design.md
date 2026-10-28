## Context

The WYSIWYG editor at `/editor/surveys/<uuid>/` is HTMX + SortableJS, with all editor JavaScript currently inline in `survey/templates/editor/survey_detail.html`. CRUD endpoints live in `survey/editor_views.py` and follow a consistent pattern: `@survey_permission_required('editor')` + `@require_POST` + `_check_structural_edit_allowed(survey)` + render an HTMX partial + emit `HX-Trigger: questionSaved`/`sectionSaved`.

**Existing clone primitives:**
- `_clone_question(question, new_section, parent)` in `survey/versioning.py:112` — private, recursive, handles translations and sub-questions. Has a latent bug: it does not copy `Question.validation_settings` (introduced after the function was written).
- Section clone logic is INLINED inside `clone_survey_for_draft()` (lines 69–107). No standalone helper exists.
- `survey/serialization.py` has independent import-side `_create_question` and `create_sections` primitives that work from JSON dicts. Not reusable here without parsing through JSON.

**Constraint introduced by issue #17 (already merged):**
- `editor_forms.py` defines `SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')`. `QuestionForm(is_subquestion=True)` strips these from `input_type` choices. The product rule is: **a sub-question SHALL NOT be a geo-type question.** This rule is enforced at the form layer for create/edit and is reflected in the canonical `survey-editor` spec under "Sub-question management for geo questions". Any new code path that creates a sub-question (specifically: paste-as-sub-question for #16) MUST enforce the same rule server-side, otherwise paste would silently bypass a constraint the form upholds.
- The "+ Add Sub-question" button now lives in `<div class="add-subquestion-wrap">` rendered below the sub-question `<ul>` inside every `point`/`line`/`polygon` question card. The "Paste as sub-question" button (introduced by this change) MUST sit in the same wrap div for visual coherence.

**Permission model:**
- `@survey_permission_required('viewer'|'editor')` decorator checks org membership + `SurveyCollaborator`.
- `_check_structural_edit_allowed(survey)` blocks structural edits on `published`/`closed` surveys, returning a 403 response.
- For cross-survey paste, the decorator covers the **target** survey only (via URL `survey_uuid`). The **source** survey must be accessed and permission-checked manually inside the view body using `get_effective_survey_role(user, source_survey)`.

**Editor JS architecture:**
- `survey_detail.html` `<script>` block already contains SortableJS init, HTMX afterSwap listeners, panel-resize logic, custom event handlers (`sectionDeleted`, `questionSaved`, `sectionSaved`, `mapPositionSaved`). ~340 lines.
- `localStorage` is already used for panel state under key `editor_panels_<survey.uuid>`.
- No existing JS module under `survey/assets/js/` is loaded by the editor.

## Goals / Non-Goals

**Goals:**
- Duplicate (sibling-insert) a section or question with a `(copy)` suffix.
- Copy a section or question to a localStorage clipboard; paste fetches the source fresh from the server.
- Cross-survey paste when permissions allow (viewer+ on source, editor on target).
- Sub-question paste semantics: promote when target is a section; allow attach when target is a `point`/`line`/`polygon` parent.
- Keyboard shortcuts: Ctrl/Cmd+D / C / V on active card.
- Carry verbatim translations; share image path (no file copy).
- Fix the `validation_settings` omission in the shared clone primitive (also fixes versioning bug).

**Non-Goals:**
- Cut/move (no in-place removal — copy + manual delete suffices).
- Multi-select duplicate.
- Bulk paste of multiple objects.
- Undo/redo.
- Server-side clipboard (no DB table for transient state).
- Cross-organization paste restriction (handled by existing permission model — no new gate).

## Decisions

### 1. New module `survey/cloning.py`; `versioning.py` delegates to it

**Decision**: Create `survey/cloning.py` with `clone_question` and `clone_section`. Refactor `versioning.py` to import and delegate.

**Rationale**:
- `versioning.py` is conceptually about draft-lifecycle (clone draft, check compatibility, publish). Adding standalone clone primitives there muddles the module's purpose. A separate `cloning.py` keeps each file cohesive and short.
- `clone_question` will have at least three callers (versioning, editor duplicate, editor paste). Centralizing it in a dedicated module makes the contract reviewable in one place.
- The `validation_settings` bug fix lands in `cloning.py` once and benefits all callers automatically.
- Trade-off vs. keeping in `versioning.py`: one extra file. Worth the cohesion benefit; the import in `versioning.py` is a one-line replacement.

**Signatures:**

```python
def clone_question(
    question: Question,
    *,
    target_section: SurveySection,
    parent: Optional[Question] = None,
    regenerate_code: bool = True,
    name_suffix: Optional[str] = None,
    copy_sub_questions: bool = True,
) -> Question:
    """Deep-clone a question into target_section.

    - regenerate_code=True calls question_code_generator() (default for editor).
      regenerate_code=False keeps the original code (versioning use case).
    - name_suffix appended to question.name if non-empty.
    - copy_sub_questions=False is used when pasting a regular question as a
      sub-question (Q8) — its own sub-questions are dropped.
    - QuestionTranslation rows are copied verbatim.
    - validation_settings is copied (was a bug in the prior _clone_question).
    - image FileField path is shared (no file copy).
    """

def clone_section(
    section: SurveySection,
    *,
    target_survey: SurveyHeader,
    insert_after: Optional[SurveySection] = None,
    name_suffix: Optional[str] = None,
) -> SurveySection:
    """Deep-clone a section into target_survey.

    - insert_after splices the new section into the linked list immediately
      after the given section. None appends at the tail. Linked-list pointers
      (prev_section, next_section, is_head) are correctly stitched.
    - name_suffix appended to section.title (and to name only if collision
      requires deduplication; section.name has no DB unique constraint but
      SurveySectionForm.clean_name enforces per-survey uniqueness).
    - SurveySectionTranslation rows copied verbatim.
    - All top-level questions cloned via clone_question(regenerate_code=True).
    - Sub-questions cloned recursively as part of clone_question.
    """
```

### 2. Four separate view functions, not one polymorphic endpoint

**Decision**: `editor_question_duplicate`, `editor_question_paste`, `editor_section_duplicate`, `editor_section_paste` are independent view functions in `editor_views.py`.

**Rationale**:
- Permission surfaces differ: paste reads from a foreign survey (extra `_can_read_survey` check); duplicate does not.
- URL inputs differ: duplicate takes `<question_id>`/`<section_id>` from the path; paste takes `source_survey_uuid` + `source_id` from the JSON body.
- HTMX response targets differ slightly (paste-as-subquestion swaps a different DOM node than top-level paste).
- A polymorphic endpoint with a `mode=` parameter would obscure all three differences and require runtime branching. Four short focused functions are clearer and more independently testable.

### 3. `_can_read_survey(user, survey)` helper, scoped to `editor_views.py`

**Decision**: Add a small private helper at the top of `editor_views.py`:

```python
def _can_read_survey(user, survey) -> bool:
    """Return True if user has at least viewer role on the survey."""
    return get_effective_survey_role(user, survey) is not None
```

**Rationale**:
- Used in both paste views; keeps source-side check uniform.
- Not generalized to `permissions.py` because it has no callers outside editor paste — premature abstraction.
- Cross-org check is intentionally NOT included (Q5 decision: viewer permission is sufficient regardless of org).

### 4. Code generation: `question_code_generator()` for every clone

**Decision**: When `regenerate_code=True`, `clone_question` calls the existing `question_code_generator()` (`Q_XXXXXXXXXX` random) for the new code. No suffix-based scheme.

**Rationale**:
- `Question.code` is an opaque programmatic identifier (default format `Q_<10digits>`) not user-facing. Suffix schemes (`q1_copy`, `q1_copy2`) look broken when the original is `Q_4827193056` and would require collision-handling logic that mirrors the existing generator.
- The user-visible "this is a copy" signal is the `(copy)` suffix on `name`/`title` (Q3), not on the code.
- Sub-questions cloned recursively also each get a fresh code (no suffix forwarding).

### 5. `(copy)` suffix only on same-container duplicate, not on paste

**Decision**:
- `editor_question_duplicate` (within same section): `name_suffix=' (copy)'`.
- `editor_section_duplicate` (within same survey): `name_suffix=' (copy)'`.
- `editor_question_paste` and `editor_section_paste` (cross-section / cross-survey): `name_suffix=None`.
- Translations are NEVER suffixed — only the base `name`/`title` field. User can edit translations manually if desired.

**Rationale**: When a clone lands in a fresh container, the name is unambiguous on its own. The "(copy)" marker is most useful when two near-identical items sit side by side.

### 6. JS module: new file `survey/assets/js/editor_clipboard.js`, loaded via static include

**Decision**: Create `survey/assets/js/editor_clipboard.js` with two IIFE-style modules:
- `Clipboard` — `copy(kind, surveyUuid, id, label)`, `peek()`, `clear()`, `paste(targetSurveyUuid, targetSectionId, parentQuestionId)`.
- `KeyboardShortcuts` — `bind(getSurveyUuid)`. Listens for Ctrl/Cmd+D/C/V on `document` and acts on the active card.

Loaded in `editor_base.html` via `<script src="{% static 'js/editor_clipboard.js' %}">`.

**Rationale**:
- The `survey_detail.html` `<script>` block is already 340+ lines. Adding ~80 more lines of clipboard + shortcut logic makes the template hard to navigate.
- A dedicated file is unit-testable in the future (vitest/jest) and avoids string-quoting issues with Django template tags inside JS.
- Trade-off: introduces an asset pipeline concern (collectstatic must run). Mitigated by the existing build workflow already running collectstatic for static files in `survey/assets/`.
- The IIFE pattern (no module bundler) matches the existing codebase — no new build step.

### 7. Active-card model: `data-active="true"` set on click

**Decision**: A delegated click handler in `editor_clipboard.js` sets `data-active="true"` on the clicked `.question-item` or `.section-item` card and removes it from siblings. After every `htmx:afterSettle` event, the handler re-applies `data-active` to the same card if it still exists in the DOM (track by ID).

**Rationale**:
- HTMX swaps replace DOM nodes — naïve focus tracking via DOM references would break after swaps. Re-applying after `afterSettle` keeps the active state stable.
- Click-to-activate is consistent with the existing section-click behavior (already loads the section detail). Hover-based activation conflicts with drag-to-reorder.
- Visual indicator: simple CSS rule `[data-active="true"] { outline: 2px solid var(--accent); }` — no new JS required.

### 8. Keyboard shortcut conflict handling

**Decision**:
- Ctrl/Cmd+C suppressed only when there is an active card AND no text selection (`window.getSelection().toString() === ''`).
- Ctrl/Cmd+V suppressed only when there is an active section card AND clipboard has a valid entry.
- Ctrl/Cmd+D always suppressed when there is an active question or section card (browser bookmark dialog is the conflict; in editor context, duplicate wins).
- All shortcuts gated by `is_read_only` flag — no shortcut binding when the survey is published/closed.

**Rationale**: Browser-native Ctrl+C must continue to work for selected text. The `getSelection()` check is the smallest correct heuristic.

### 9. Sibling-insert mechanics

**Decision (questions)**: `editor_question_duplicate` and `editor_question_paste` insert the new question with `order_number = source.order_number + 1`. All siblings with `order_number > source.order_number` are shifted by `+1` in a single SQL UPDATE inside the transaction. (When pasting into a different section, `order_number = max(target_section_orders) + 1` — no shift needed.)

**Decision (sections)**: `clone_section(section, target_survey, insert_after=section)` performs a 3-node splice: `insert_after.next → new`, `new.next → old_next`, with `prev_section` updated symmetrically. `is_head` always False on the clone. If `insert_after=None`, append at tail.

**Rationale**: Sibling-insert is the user expectation (Q1). The shift cost is `O(N)` per section but N is small (typical sections have <30 questions). One transactional UPDATE keeps it atomic.

### 10. Paste affordances and discoverability

**Decision**:
- The "Paste question here" button appears in the section detail panel header next to "+ New Question". It is rendered always, but JS shows/hides it based on `Clipboard.peek()?.kind === 'question'`.
- The "Paste section" button appears in the sidebar near "+ New Section". Same JS show/hide logic.
- A "Paste as sub-question" button is rendered **inside** the existing `<div class="add-subquestion-wrap">` (introduced by issue #17) on every `point`/`line`/`polygon` question card. The button sits next to the existing "+ Add Sub-question" button. Visible only when clipboard has `kind === 'question'` AND the source's `input_type` is non-geo (per the rule from #17 — see Decision 11 below).
- Tooltip on each paste button shows the clipboard label and `copied X minutes ago`.

**Rationale**: Discoverability matters more than terseness for a non-obvious feature. The keyboard shortcuts (Q11) provide the power-user path; visible buttons provide discoverability.

### 11. Sub-question type constraint on paste-as-sub-question

**Decision**: `editor_question_paste`, when invoked with a `parent_question_id` (paste-as-sub-question target), MUST validate that the source question's `input_type` is NOT in `SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')`. If the constraint is violated, the view returns HTTP 400 with a validation error and does not mutate the database. The frontend "Paste as sub-question" button MUST be hidden (or rendered disabled with an explanatory tooltip) when the clipboard's `kind === 'question'` but the source's input_type is geo — to avoid sending requests that will fail.

**Rationale**: Issue #17 introduced the rule "a sub-question cannot be a geo question" and enforced it in `QuestionForm` for create/edit. The paste path bypasses the form, so the rule must be re-enforced explicitly in the view; otherwise paste would create database state that the editor's edit form refuses to round-trip. The rule applies symmetrically: paste as top-level (`parent_question_id=None`) does NOT enforce the constraint — geo questions can be top-level.

**Implementation**: The clipboard payload (`localStorage.editor_clipboard`) includes the source's `input_type` as part of the cached `label` data. Frontend uses this to gate button visibility client-side; server-side check is the source-of-truth (defends against stale clipboards and crafted requests).

## Risks / Trade-offs

- **Linked-list correctness**: Sibling-insert in sections is a 3-node splice, not covered by existing tests. Mitigation: unit-test `clone_section` in isolation with a 3-section fixture; cover the `insert_after = head`, `insert_after = middle`, `insert_after = tail`, `insert_after = None` cases.
- **`order_number` shift bug risk**: Forgetting the shift would create two questions with the same `order_number`, leading to non-deterministic ordering. Mitigation: explicit test asserting all order_numbers are distinct after duplicate.
- **Cross-survey paste with stale clipboard**: User copies, then deletes the source survey, then pastes — `editor_question_paste` returns 404. Frontend must handle the 404 by clearing the clipboard and showing an error toast.
- **HTMX swap re-applies SortableJS but loses click handlers**: Existing pattern (`htmx:afterSettle` re-init) handles SortableJS. The clipboard module's click delegation uses `document.addEventListener('click', ...)` which is not affected by swaps. No regression.
- **Image path sharing edge case**: If the original question's image is later deleted from storage, the duplicate's image path becomes stale. This is a pre-existing pattern in `versioning.py` clone — not made worse here.
- **Clipboard TTL**: localStorage entries persist forever by design. A user who copied a week ago still sees the paste button on next session. Mitigation: show `copied_at` in tooltip ("copied 2 days ago") so user can decide; no automatic expiry to keep behavior predictable.
- **`Question.code` global uniqueness**: `question_code_generator()` checks global uniqueness via `Question.objects.get(code=code)` in a loop. With high concurrency this is racy — two parallel duplicates could get the same code. Acceptable for editor-rate operations; existing behavior in `editor_question_create` has the same risk.

## Migration Plan

### Phase 1 — Backend primitives (`survey/cloning.py`)
1. Create `survey/cloning.py` with `clone_question` and `clone_section`. Include `validation_settings` in the question copy. Match signatures above exactly.
2. Run existing test suite — no callers yet, no regressions expected.

### Phase 2 — Refactor `survey/versioning.py`
3. Replace the private `_clone_question` import/definition: import `clone_question as clone_question_v` from `cloning`, drop the local definition, update `clone_survey_for_draft` to call `clone_question(question, target_section=new_section, parent=parent, regenerate_code=False)`.
4. Replace the inlined section-create block in `clone_survey_for_draft` with `clone_section(section, target_survey=draft, insert_after=...)` (resolving `insert_after` from `old_to_new_section` mapping). The second-pass linked-list resolution remains for `next_section` forward-link if needed.
5. Run existing versioning tests — they assert clone behavior; expect them to pass with `validation_settings` now copied (no test currently asserts it's dropped).

### Phase 3 — New view functions and URLs
6. Add `_can_read_survey(user, survey)` helper to `editor_views.py`.
7. Add `editor_question_duplicate(request, survey_uuid, question_id)`.
8. Add `editor_section_duplicate(request, survey_uuid, section_id)`.
9. Add `editor_question_paste(request, survey_uuid, section_id)` (URL takes target section; body takes source).
10. Add `editor_section_paste(request, survey_uuid)` (URL takes target survey only; body takes source survey + source section).
11. Add 4 URL routes to `survey/urls.py`.

### Phase 4 — Frontend module
12. Create `survey/assets/js/editor_clipboard.js` with `Clipboard` and `KeyboardShortcuts` IIFE modules.
13. Add `<script src="{% static 'js/editor_clipboard.js' %}"></script>` to `templates/editor/editor_base.html`.
14. Add active-card CSS rule to `survey/assets/css/editor.css` (or whatever the editor stylesheet is).
15. Run `python manage.py collectstatic` (will be auto-run in CI).

### Phase 5 — Templates
16. Add Duplicate + Copy buttons to `partials/question_list_item.html` (Duplicate uses HTMX; Copy uses inline `onclick="Clipboard.copy(...)"`).
17. Add Duplicate + Copy buttons to `partials/section_list_item.html`.
18. Add "Paste question here" button to `partials/section_detail_form.html` next to `+ New Question` (initially hidden by JS).
19. Add "Paste section" button to `survey_detail.html` sidebar (initially hidden).
20. Add "Paste as sub-question" button to `partials/question_list_item.html` for `point`/`line`/`polygon` cards.

### Phase 6 — Tests
21. Add `EditorQuestionDuplicateTest` (same-section, with sub-questions, validation_settings preserved, "(copy)" suffix, sibling order, new code).
22. Add `EditorSectionDuplicateTest` (linked-list correctness with insert_after at head/middle/tail; questions and translations cloned; "(copy)" suffix on title).
23. Add `EditorQuestionPasteTest` (same-survey, cross-survey, sub-question promotion, regular-as-sub-question demotion, permission gate).
24. Add `EditorSectionPasteTest` (same-survey equals duplicate; cross-survey; permission gate).
25. Add `CloningPrimitiveTest` covering `clone_question` and `clone_section` directly with all flag combinations.

### Phase 7 — Manual smoke
26. Open editor in two browser tabs on different surveys; copy a question in tab A; paste in tab B; verify the question appears with new code.
27. Verify Ctrl/Cmd+D, C, V work; verify Ctrl+C still copies selected text when no card is active.
28. Verify paste blocked on published survey with proper error.

## Open Questions

- **OQ1**: Should the "Paste as sub-question" button appear on every geo-question card always, or only when clipboard is non-empty? Always-visible would also serve as a discoverability hint that sub-questions can be pasted. Likely: visible always but disabled with tooltip "Copy a question first" when clipboard empty. Resolve during template implementation.
- **OQ2**: Does `clone_section` need to deduplicate `name` automatically (like `editor_section_create` does for `section_N`)? `SurveySectionForm.clean_name` enforces per-survey uniqueness, but `clone_section` bypasses the form. Decision: yes — `clone_section` generates a unique name on collision (append `_2`, `_3`, …). Documented in the function docstring.
- **OQ3**: Should we add an "active card" outline as a visual indicator of focus, or rely solely on click-to-edit feedback? Decision: yes, add a subtle outline (CSS `[data-active="true"] { outline: 2px solid var(--accent-light); }`) so keyboard shortcut users know which card is active. Confirm color choice during implementation.
- **OQ4**: Should the OpenSpec change touch the `survey-versioning` capability spec? The canonical spec for `survey-versioning` does not exist in `openspec/specs/` (only an archived change spec). Decision: include the `validation_settings` bug-fix scenario in the `survey-editor` delta as a regression-prevention scenario, since adding a new top-level capability requires more ceremony than this fix warrants.
