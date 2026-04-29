## Why

Survey authors frequently build similar sections and questions in the WYSIWYG editor (`/editor/surveys/<uuid>/`). Today they must recreate them by hand — there is no way to copy a section's questions into another section, or duplicate a question to use it as a starting point for a variant. This is the most-asked editor ergonomics request (issue #16). It also affects users coming from competitors (Google Forms, Maptionnaire) where duplicate is a baseline expectation.

## What Changes

- Add a **Duplicate** action on every section card and question card (including sub-questions). Duplicate creates a clone immediately after the source (sibling-insert) with a `(copy)` suffix on the name/title.
- Add a **Copy / Paste** flow using a `localStorage`-backed clipboard (key `editor_clipboard`). The buffer holds references `{kind, source_survey_uuid, source_id, label, copied_at}` — paste fetches the source fresh from the server. The clipboard is shared across browser tabs of the same origin, so a user can copy in one tab and paste in another tab editing a different survey.
- Add **keyboard shortcuts** while a question or section card is the active card: `Ctrl/Cmd+D` duplicates, `Ctrl/Cmd+C` copies, `Ctrl/Cmd+V` pastes.
- **Sub-question semantics**: pasting a sub-question directly into a section promotes it to a top-level question. Pasting a regular question under a `point`/`line`/`polygon` parent attaches it as a sub-question (the source's own sub-questions are dropped in this case).
- **Cross-survey paste**: allowed when the user has at least viewer permission on the source survey AND editor permission on the target survey. No same-organization restriction.
- **Read-only locking**: paste/duplicate into `published` or `closed` surveys is blocked by the existing `_check_structural_edit_allowed` gate. Source surveys may have any status.
- **Bug fix bundled**: `validation_settings` is currently dropped by `_clone_question` in `versioning.py` — the new shared `clone_question` primitive copies it correctly, fixing a latent bug in the draft-copy workflow.

## Capabilities

### New Capabilities
- `editor-clipboard`: localStorage-backed clipboard for sections and questions; cross-tab and cross-survey paste with server-side permission validation.
- `editor-duplicate`: in-place sibling-insert duplicate of sections and questions with `(copy)` suffix.

### Modified Capabilities
- `survey-editor`: new buttons in section/question card kebab menus; keyboard shortcuts on active cards; new endpoints for duplicate and paste; "active card" tracking added to editor JS.

## Impact

- **New module**: `survey/cloning.py` — `clone_question(question, *, target_section, parent=None, regenerate_code=True, name_suffix=None)` and `clone_section(section, *, target_survey, insert_after=None, name_suffix=None)`. Single source of truth for all clone operations.
- **Refactor**: `survey/versioning.py` delegates to `survey/cloning.py`. The private `_clone_question` is removed; the inlined section clone block in `clone_survey_for_draft` is replaced with a `clone_section` call. The `validation_settings` field is now copied (bug fix as side effect).
- **Views**: `survey/editor_views.py` gains four endpoints — `editor_question_duplicate`, `editor_question_paste`, `editor_section_duplicate`, `editor_section_paste`. A small helper `_can_read_survey(user, survey)` wraps the source-side permission check.
- **URLs**: 4 new routes in `survey/urls.py`.
- **JS**: New file `survey/assets/js/editor_clipboard.js` — exports `Clipboard` and `KeyboardShortcuts` modules. Loaded once in `editor_base.html`.
- **Templates**: Duplicate/Copy buttons added to `partials/question_list_item.html` and `partials/section_list_item.html`. Paste affordance added to `partials/section_detail_form.html` (paste-question) and section sidebar (paste-section).
- **Tests**: New test classes in `survey/tests.py` covering duplicate, paste-same-survey, paste-cross-survey, sub-question promotion/demotion, validation_settings preservation, permission gates.
- **Migrations**: None. No model changes.
- **Backward compatibility**: `_clone_question` callers (currently only `clone_survey_for_draft`) continue to work unchanged after the rename — keyword arguments default to versioning-compatible behavior (`regenerate_code=False`, `name_suffix=None`).
