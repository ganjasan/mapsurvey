## 1. Template

- [x] 1.1 In `survey/templates/editor/partials/question_list_item.html`, remove the `fa-sitemap` icon button block from the `.q-actions` row (the conditional block currently rendered for `point`/`line`/`polygon` questions, between the edit and delete buttons).
- [x] 1.2 In the same template, after the existing `{% if sub_questions %}<ul class="subquestion-list">…</ul>{% endif %}` block, add a `{% if question.input_type == 'point' or … 'line' or … 'polygon' %}` block that renders a `<div class="add-subquestion-wrap">` containing a `<button class="add-question-btn add-question-btn--sub">…</button>`.
- [x] 1.3 Wire the button: `hx-get="{% url 'editor_subquestion_create' survey.uuid question.id %}"`, `hx-target="#questionModalBody"`, `hx-swap="innerHTML"`, `data-toggle="modal" data-target="#questionModal"`, plus the read-only branch (`{% if not is_read_only %}…{% else %}disabled{% endif %}`) and the `title="{% if is_read_only %}Create a draft to edit{% else %}Add Sub-question{% endif %}"` tooltip.
- [x] 1.4 Button content: `<i class="fas fa-plus"></i> Add Sub-question`.

## 2. CSS

- [x] 2.1 In `survey/templates/editor/editor_base.html`, add a `.add-subquestion-wrap` rule with `padding: 0.5rem 0.75rem 0.5rem 2.5rem;` (matches the `.subquestion-list` left-indent so the button aligns with sub-question rows).
- [x] 2.2 Add `.question-item-row + .add-subquestion-wrap { border-top: 1px dashed var(--border-color); }` so the empty-list case still has a visual separator (when a sub-question list is rendered above, its own `border-top` already provides one).
- [x] 2.3 Add `.add-question-btn--sub { padding: 0.5rem 0.75rem; font-size: 0.8rem; border-width: 1px; }` to right-size the button for the nested context while keeping the dashed-border / accent-on-hover / disabled rules from `.add-question-btn`.

## 3. Sub-question type filter (form layer)

- [x] 3.1 In `survey/editor_forms.py`, declare `SUBQUESTION_DISALLOWED_INPUT_TYPES = ('point', 'line', 'polygon')` at module scope so the constant has a single source of truth.
- [x] 3.2 In `QuestionForm.__init__`, accept `is_subquestion: bool = False` (keyword-only). When true, replace `self.fields['input_type'].choices` with the same list filtered to drop entries whose value is in `SUBQUESTION_DISALLOWED_INPUT_TYPES`. Django's built-in `ChoiceField` validation then rejects POSTs that submit a filtered value.
- [x] 3.3 In `survey/editor_views.py::editor_subquestion_create`, instantiate `QuestionForm(..., is_subquestion=True)` for both the GET (modal render) and POST (validation) branches.
- [x] 3.4 In `survey/editor_views.py::editor_question_edit`, compute `is_subquestion = question.parent_question_id_id is not None` once after fetching the question, and pass it to both the GET and POST `QuestionForm` instantiations. Top-level question edits keep all geo options.

## 4. Tests

- [x] 4.1 Extend `EditorSubquestionTest` with `test_add_subquestion_button_visible_on_geo_question`: GIVEN a draft survey with a `point` question; WHEN the editor section detail is fetched; THEN the response HTML contains "Add Sub-question" and an `hx-get` URL pointing at `editor_subquestion_create` for that question.
- [x] 4.2 Add `test_add_subquestion_button_absent_on_non_geo_question`: GIVEN a draft survey with a `text` question; WHEN the editor section detail is fetched; THEN the response HTML does NOT contain the corresponding `editor_subquestion_create` URL for that text question.
- [x] 4.3 Add `test_add_subquestion_button_disabled_in_readonly`: GIVEN a published survey with a `point` question; WHEN the editor section detail is fetched; THEN the "Add Sub-question" button is rendered with the `disabled` attribute and the "Create a draft to edit" tooltip, and carries no `hx-get` URL.
- [x] 4.4 Add `test_legacy_sitemap_icon_removed`: GIVEN any geo question card; WHEN rendered; THEN the response HTML does NOT contain `fa-sitemap`.
- [x] 4.5 Add `test_subquestion_create_form_excludes_geo_input_types`: GIVEN a geo question; WHEN the new sub-question modal is opened; THEN the rendered `<select name="input_type">` contains no `value="point"`, `value="line"`, `value="polygon"` options (and still contains `value="text"`, `value="choice"`).
- [x] 4.6 Add `test_subquestion_create_rejects_geo_input_types`: GIVEN a geo question; WHEN a POST submits `input_type=point` to `editor_subquestion_create`; THEN no Question is created (count unchanged) and the form modal is re-rendered (status 200).
- [x] 4.7 Add `test_subquestion_edit_form_excludes_geo_input_types`: GIVEN an existing non-geo sub-question; WHEN its edit modal is fetched; THEN the input_type select offers no geo options.
- [x] 4.8 Add `test_top_level_question_edit_form_keeps_geo_input_types`: GIVEN a top-level geo question; WHEN its edit modal is fetched; THEN the input_type select still offers `point`, `line`, `polygon` so top-level editing is unchanged.

## 5. Verification

- [x] 5.1 Run `./run_tests.sh survey.tests.EditorSubquestionTest -v2` and confirm all 9 tests pass.
- [x] 5.2 Run the full editor regression suite (`EditorAuthTest`, `EditorSurveyCreateTest`, `EditorSectionCRUDTest`, `EditorSectionReorderTest`, `EditorQuestionCRUDTest`, `EditorQuestionReorderTest`, `EditorSubquestionTest`, `EditorPermissionTest`, `EditorTransitionTest`, `EditorVersioningEndpointsTest`) and confirm all 49 tests pass.
- [x] 5.3 Run `openspec validate add-prominent-add-subquestion-button` and confirm no validation errors.
