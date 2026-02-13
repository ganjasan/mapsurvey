## 1. Foundation and URL routing

- [ ] 1.1 Create `survey/editor_views.py` with stub views for all editor endpoints
- [ ] 1.2 Create `survey/editor_forms.py` with `SurveyHeaderForm`, `SurveySectionForm`, `QuestionForm`
- [ ] 1.3 Add all editor URL patterns to `survey/urls.py`
- [ ] 1.4 Create `survey/templates/editor/editor_base.html` extending `base.html` with HTMX and SortableJS CDN includes

## 2. Dashboard integration

- [ ] 2.1 Wire "New Survey" button in `editor.html` to link to `/editor/surveys/new/`
- [ ] 2.2 Wire "Edit" link for each survey to `/editor/surveys/<name>/`

## 3. Survey creation

- [ ] 3.1 Implement `editor_survey_create` view (GET: render form, POST: create SurveyHeader + default section, redirect to editor)
- [ ] 3.2 Create `survey/templates/editor/survey_create.html` with `SurveyHeaderForm`
- [ ] 3.3 Add validation: reject duplicate survey names, require name field

## 4. Survey editor main page

- [ ] 4.1 Implement `editor_survey_detail` view that loads survey, sections in linked-list order, and current section's questions
- [ ] 4.2 Create `survey/templates/editor/survey_detail.html` with 3-column layout (sidebar, center, preview)
- [ ] 4.3 Create `survey/templates/editor/partials/section_list_item.html` for sidebar section entries
- [ ] 4.4 Add CSS for the 3-column editor layout

## 5. Section CRUD

- [ ] 5.1 Implement `editor_section_create` view (POST, returns section_list_item partial, appends to linked list)
- [ ] 5.2 Implement `editor_section_detail` view (GET returns section form partial via HTMX)
- [ ] 5.3 Create `survey/templates/editor/partials/section_detail_form.html` with title, subheading, code fields
- [ ] 5.4 Implement section save (POST: update title, subheading, code)
- [ ] 5.5 Implement `editor_section_delete` view (POST, re-links neighbors, removes from DOM)

## 6. Section reordering

- [ ] 6.1 Implement `editor_sections_reorder` view (POST: receives ordered section IDs, rebuilds linked list in transaction)
- [ ] 6.2 Initialize SortableJS on sections sidebar with drag handle and onEnd callback

## 7. Question CRUD

- [ ] 7.1 Implement `editor_question_create` view (GET: return modal form, POST: create question, return question_list_item partial)
- [ ] 7.2 Create `survey/templates/editor/partials/question_form_modal.html` with all question fields
- [ ] 7.3 Create `survey/templates/editor/partials/question_list_item.html` with type badge, edit/delete buttons
- [ ] 7.4 Implement `editor_question_edit` view (GET: return pre-filled modal, POST: update question)
- [ ] 7.5 Implement `editor_question_delete` view (POST, removes question, returns empty for HTMX outerHTML swap)

## 8. Question reordering

- [ ] 8.1 Implement `editor_questions_reorder` view (POST: receives ordered question IDs, updates order_number)
- [ ] 8.2 Initialize SortableJS on question list with drag handle and onEnd callback

## 9. Choices editor

- [ ] 9.1 Create `survey/templates/editor/partials/question_choices_editor.html` with dynamic add/remove rows
- [ ] 9.2 Add JS to show/hide choices editor based on input_type selection (choice, multichoice, range, rating)
- [ ] 9.3 Add JS to serialize choice rows to JSON on form submit (code + multilingual name fields → Question.choices format)
- [ ] 9.4 Populate choices editor with existing choices when editing a question

## 10. Sub-question management

- [ ] 10.1 Implement `editor_subquestion_create` view (GET: modal form, POST: create question with parent_question_id set)
- [ ] 10.2 Show "Add Sub-question" button only on geo questions (point, line, polygon) in question_list_item
- [ ] 10.3 Display sub-questions nested under their parent in the question list
- [ ] 10.4 Support editing and deleting sub-questions (reuse question edit/delete views with parent context)

## 11. Section map position picker

- [ ] 11.1 Implement `editor_section_map_picker` view (GET: render Leaflet map modal, POST: save position and zoom)
- [ ] 11.2 Create `survey/templates/editor/partials/section_map_picker.html` with Leaflet map, click-to-set marker, zoom capture
- [ ] 11.3 Add "Set Map Position" button to section detail form

## 12. Translation management

- [ ] 12.1 Add translation fields to section detail form (one set of title/subheading fields per available language)
- [ ] 12.2 Add translation fields to question form modal (one set of name/subtext fields per available language)
- [ ] 12.3 Save/update SurveySectionTranslation and QuestionTranslation records on form submit

## 13. Survey settings

- [ ] 13.1 Implement `editor_survey_settings` view (GET: render settings form, POST: update SurveyHeader)
- [ ] 13.2 Create `survey/templates/editor/survey_settings_modal.html` with all SurveyHeader fields
- [ ] 13.3 Add "Settings" button to editor sidebar header that opens settings modal via HTMX

## 14. Live preview

- [ ] 14.1 Implement `editor_section_preview` view that renders survey_section.html with preview=True context flag
- [ ] 14.2 Add preview=True handling in survey_section.html to disable form submission and hide navigation buttons
- [ ] 14.3 Add iframe to the right panel of survey_detail.html pointing to preview URL
- [ ] 14.4 Add JS to reload preview iframe after every HTMX swap (debounced 500ms)

## 15. Testing

- [ ] 15.1 Test survey creation (happy path + duplicate name rejection)
- [ ] 15.2 Test section CRUD (create, edit, delete, linked-list integrity)
- [ ] 15.3 Test section reordering (linked list rebuilt correctly)
- [ ] 15.4 Test question CRUD (create all input types, edit, delete)
- [ ] 15.5 Test question reordering (order_number updated correctly)
- [ ] 15.6 Test choices editor (serialization to JSONField, multilingual names)
- [ ] 15.7 Test sub-question creation and parent relationship
- [ ] 15.8 Test authentication requirement on all editor views
