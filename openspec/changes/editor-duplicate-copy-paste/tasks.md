## 1. Backend primitives — `survey/cloning.py`

- [ ] 1.1 Create `survey/cloning.py` with `clone_question(question, *, target_section, parent=None, regenerate_code=True, name_suffix=None, copy_sub_questions=True) -> Question`
- [ ] 1.2 Implement question field copy: `code` (regenerated if flag), `order_number`, `name` (with optional suffix), `subtext`, `input_type`, `choices`, `required`, `validation_settings`, `color`, `icon_class`, `image` (path shared)
- [ ] 1.3 Implement `QuestionTranslation` row copy verbatim
- [ ] 1.4 Implement recursive sub-question cloning when `copy_sub_questions=True`
- [ ] 1.5 Add `clone_section(section, *, target_survey, insert_after=None, name_suffix=None) -> SurveySection` to `survey/cloning.py`
- [ ] 1.6 Implement section field copy: `name` (deduplicated within target survey), `title` (with optional suffix), `subheading`, `code`, `start_map_postion`, `start_map_zoom`, `use_geolocation`, `override_basemap`, `is_head=False`
- [ ] 1.7 Implement linked-list 3-node splice with `insert_after` (and tail-append fallback when None)
- [ ] 1.8 Implement `SurveySectionTranslation` row copy verbatim
- [ ] 1.9 Implement top-level question cloning via `clone_question(regenerate_code=True)`
- [ ] 1.10 Add module docstring and per-function docstrings explaining flags

## 2. Refactor `survey/versioning.py`

- [ ] 2.1 Import `clone_question` from `survey.cloning` (alias as needed)
- [ ] 2.2 Remove the private `_clone_question` definition
- [ ] 2.3 Update `clone_survey_for_draft` to call `clone_question(question, target_section=new_section, parent=parent, regenerate_code=False)` (preserves codes for versioning)
- [ ] 2.4 Replace inlined section-create block with `clone_section(section, target_survey=draft, insert_after=resolved_prev)` calls
- [ ] 2.5 Verify the `next_section` resolution second-pass still functions correctly after the refactor
- [ ] 2.6 Run existing versioning tests — verify all pass

## 3. View functions — `survey/editor_views.py`

- [ ] 3.1 Add `_can_read_survey(user, survey) -> bool` helper using `get_effective_survey_role`
- [ ] 3.2 Implement `editor_question_duplicate(request, survey_uuid, question_id)`: editor permission + structural-edit gate; clone with `regenerate_code=True`, `name_suffix=' (copy)'`; insert at `source.order_number + 1` with shift-down; return `question_list_item.html` partial + `HX-Trigger: questionSaved`
- [ ] 3.3 Implement `editor_section_duplicate(request, survey_uuid, section_id)`: editor permission + structural-edit gate; `clone_section(insert_after=source, name_suffix=' (copy)')`; return `section_list_item.html` partial + `HX-Trigger: sectionSaved`
- [ ] 3.4 Implement `editor_question_paste(request, survey_uuid, section_id)`: editor permission on target + structural-edit gate; read `source_survey_uuid`, `source_question_id`, `parent_question_id` (optional) from JSON body; verify viewer+ on source via `_can_read_survey`; apply Q7/Q8 promotion/demotion logic; clone with `regenerate_code=True`, `name_suffix=None`; return appropriate partial
- [ ] 3.5 Implement `editor_section_paste(request, survey_uuid)`: editor permission on target + structural-edit gate; read `source_survey_uuid`, `source_section_id` from JSON body; verify viewer+ on source; clone with `name_suffix=None` and append at tail; return `section_list_item.html` partial
- [ ] 3.6 Wrap all four views in `transaction.atomic()`

## 4. URL routing — `survey/urls.py`

- [ ] 4.1 Add `path('editor/surveys/<uuid:survey_uuid>/questions/<int:question_id>/duplicate/', editor_views.editor_question_duplicate, name='editor_question_duplicate')`
- [ ] 4.2 Add `path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/duplicate/', editor_views.editor_section_duplicate, name='editor_section_duplicate')`
- [ ] 4.3 Add `path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/paste-question/', editor_views.editor_question_paste, name='editor_question_paste')`
- [ ] 4.4 Add `path('editor/surveys/<uuid:survey_uuid>/paste-section/', editor_views.editor_section_paste, name='editor_section_paste')`

## 5. Frontend — `survey/assets/js/editor_clipboard.js`

- [ ] 5.1 Create `survey/assets/js/editor_clipboard.js` with `Clipboard` IIFE module exposing `copy(kind, surveyUuid, id, label)`, `peek()`, `clear()`, `paste(targetSurveyUuid, targetSectionId, parentQuestionId)`
- [ ] 5.2 `Clipboard.copy` writes `{kind, source_survey_uuid, source_id, label, copied_at}` to `localStorage.editor_clipboard`
- [ ] 5.3 `Clipboard.paste` POSTs JSON to the appropriate paste endpoint with CSRF token; handles 404 by clearing clipboard and showing toast
- [ ] 5.4 Implement `KeyboardShortcuts` IIFE: `bind(getSurveyUuid)` registers `keydown` listener for Ctrl/Cmd+D / C / V on `document`
- [ ] 5.5 Implement active-card tracking: delegated `click` handler sets `data-active="true"` on `.question-item` / `.section-item`; removes from siblings; re-applies after `htmx:afterSettle`
- [ ] 5.6 Implement Ctrl/Cmd+C suppression: only act when `getSelection().toString() === ''` and active card exists
- [ ] 5.7 Implement Ctrl/Cmd+V: only act when active section card exists and clipboard has valid entry
- [ ] 5.8 Implement Ctrl/Cmd+D: only act when active question or section card exists
- [ ] 5.9 Implement paste-button visibility toggling: scan DOM for `.paste-question-btn`, `.paste-section-btn`, `.paste-as-subquestion-btn`; show/hide based on `Clipboard.peek()` kind
- [ ] 5.10 Implement tooltip `copied X minutes ago` based on `copied_at` timestamp

## 6. Templates

- [ ] 6.1 In `partials/question_list_item.html`: add Duplicate button (HTMX POST to `editor_question_duplicate`) and Copy button (`onclick="Clipboard.copy('question', ...)"`) to `.q-actions`; both gated by `{% if not is_read_only %}`
- [ ] 6.2 In `partials/question_list_item.html`: for `point`/`line`/`polygon` cards, add "Paste as sub-question" button (initially `display:none`)
- [ ] 6.3 In `partials/section_list_item.html`: add Duplicate and Copy buttons next to delete
- [ ] 6.4 In `partials/section_detail_form.html`: add "Paste question here" button next to "+ New Question" (initially `display:none`)
- [ ] 6.5 In `survey_detail.html`: add "Paste section" button next to "+ New Section" in sidebar (initially `display:none`)
- [ ] 6.6 In `editor_base.html`: add `<script src="{% static 'js/editor_clipboard.js' %}"></script>` after Bootstrap and before SortableJS init blocks
- [ ] 6.7 In `survey_detail.html` extra_scripts block: call `Clipboard.bindPasteButtonsVisibility()` and `KeyboardShortcuts.bind('{{ survey.uuid }}')` on DOMContentLoaded; gate behind `{% if not is_read_only %}`
- [ ] 6.8 Add CSS rule for `[data-active="true"]` outline (subtle accent color)

## 7. Tests — `survey/tests.py`

- [ ] 7.1 `CloningPrimitiveTest.test_clone_question_copies_validation_settings` — clone preserves the JSON dict
- [ ] 7.2 `CloningPrimitiveTest.test_clone_question_regenerates_code_when_flag_true` — new code is unique and not equal to source
- [ ] 7.3 `CloningPrimitiveTest.test_clone_question_name_suffix` — suffix appended to name, not to translations
- [ ] 7.4 `CloningPrimitiveTest.test_clone_question_with_subquestions` — sub-questions cloned recursively with new codes; `copy_sub_questions=False` drops them
- [ ] 7.5 `CloningPrimitiveTest.test_clone_section_inserts_after_at_head_middle_tail` — linked-list integrity in all three positions
- [ ] 7.6 `CloningPrimitiveTest.test_clone_section_appends_at_tail_when_none` — when `insert_after=None`
- [ ] 7.7 `CloningPrimitiveTest.test_clone_section_dedups_name` — collision triggers `_2`/`_3` suffix
- [ ] 7.8 `EditorQuestionDuplicateTest.test_duplicate_question_creates_sibling_with_copy_suffix`
- [ ] 7.9 `EditorQuestionDuplicateTest.test_duplicate_shifts_subsequent_order_numbers`
- [ ] 7.10 `EditorQuestionDuplicateTest.test_duplicate_blocked_on_published_survey` — 403 expected
- [ ] 7.11 `EditorSectionDuplicateTest.test_duplicate_section_clones_questions_and_translations`
- [ ] 7.12 `EditorSectionDuplicateTest.test_duplicate_inserts_into_linked_list_immediately_after`
- [ ] 7.13 `EditorQuestionPasteTest.test_paste_same_survey`
- [ ] 7.14 `EditorQuestionPasteTest.test_paste_cross_survey_with_viewer_permission`
- [ ] 7.15 `EditorQuestionPasteTest.test_paste_cross_survey_without_permission_returns_404`
- [ ] 7.16 `EditorQuestionPasteTest.test_paste_subquestion_into_section_promotes_to_top_level`
- [ ] 7.17 `EditorQuestionPasteTest.test_paste_regular_into_geo_parent_attaches_as_subquestion`
- [ ] 7.18 `EditorSectionPasteTest.test_paste_section_cross_survey`
- [ ] 7.19 `EditorSectionPasteTest.test_paste_section_blocked_on_published_target`
- [ ] 7.20 `VersioningRegressionTest.test_clone_survey_for_draft_preserves_validation_settings` — regression test for the bug fix

## 8. Manual smoke

- [ ] 8.1 Open editor in two browser tabs on different surveys; copy question in tab A; paste in tab B; verify clone appears with new code
- [ ] 8.2 Verify Ctrl/Cmd+D duplicates active question card; Ctrl/Cmd+D on active section duplicates section
- [ ] 8.3 Verify Ctrl/Cmd+C with active card copies; Ctrl/Cmd+C with text selection still copies text (no double-handling)
- [ ] 8.4 Verify Ctrl/Cmd+V pastes when active section + clipboard has question
- [ ] 8.5 Verify paste blocked with proper error toast when target survey is published
- [ ] 8.6 Verify "(copy)" suffix appears on duplicate-in-place but NOT on cross-survey paste
- [ ] 8.7 Verify validation_settings persist after duplicate of a number/text question with min/max set
- [ ] 8.8 Verify image displays in cloned question (path shared, not broken)
