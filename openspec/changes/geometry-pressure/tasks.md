# Tasks: geometry-pressure

## 1. Model & Migration

- [x] Add `("pressure", _("Geometry Pressure"))` to `INPUT_TYPE_CHOICES` in `survey/models.py`
- [x] Add `geometries = models.JSONField(null=True, blank=True)` to `Question` model
- [x] Add `geometry_id = models.CharField(max_length=50, null=True, blank=True)` to `Answer` model
- [x] Update `SurveyHeader.geo_questions()` to include `'pressure'` in the `input_type__in` filter
- [x] Run `makemigrations` and verify the migration file

## 2. Form & Widget

- [x] Create `PressureButtonWidget` class in `survey/forms.py` — subclass of `LeafletDrawButtonWidget`, template `pressure_button.html`, adds `geometries` to context
- [x] Create `PressureField` class in `survey/forms.py` — subclass of `LeafletDrawButtonField`, accepts `geometries` param, passes to widget via `widget_attrs`
- [x] Add `pressure` branch to `_get_form_from_input_type()` returning `PressureField` with `PressureButtonWidget`
- [x] Create template `survey/templates/pressure_button.html` — same layout as `leaflet_draw_button.html` but with CSS class `pressurebutton`, `data-geometries` attribute, `fas fa-hand-pointer` icon, hidden `geo-inp` input

## 3. Respondent-Side JavaScript

- [x] Add pressure shape rendering in `base_survey_template.html` — on map init, find `.pressurebutton` elements, parse `data-geometries`, create Leaflet layers (marker/polyline/polygon) in a separate `featureGroup` per question, set initial 0.5 opacity
- [x] Add click handler on each predefined layer — open popup with sub-question form (`subquestions_forms[questionCode]`), unique form ID `subquestion_form_<geometry_id>`
- [x] Add popup open/close handlers — populate form fields from `layer.feature.properties` on open (reuse `onPopupOpen` pattern), serialize back on close/apply (reuse `onPopupClose` pattern)
- [x] Add visual feedback — track answered shapes in `pressureAnswered` Set, update opacity to 1.0 and add checkmark badge on answered shapes
- [x] Add form submission handler for pressure — iterate pressure featureGroups, serialize answered layers to pipe-delimited GeoJSON in `geo-inp` hidden input (include `geometry_id` in properties)

## 4. Existing Answer Restoration

- [x] In `survey_section.html` existing geo answers loop, detect pressure questions (check for `.pressurebutton` with matching question code), match features to predefined layers by `geometry_id`, copy properties, mark as answered

## 5. View — POST (Answer Saving)

- [x] Extend geo-save condition in `survey/views.py` `survey_section` POST to include `'pressure'`
- [x] For pressure questions, dispatch geometry type from GeoJSON `geometry.type` (Point→answer.point, LineString→answer.line, Polygon→answer.polygon)
- [x] Extract `geometry_id` from `gj['properties']['geometry_id']`, set on answer and sub-answers
- [x] Add upsert logic: before creating Answer, check for existing Answer with same `(survey_session, question, geometry_id)` — update if found

## 6. View — GET (Answer Loading)

- [x] Extend existing_geo_answers block in `survey/views.py` to include `pressure` in the `input_type in (...)` check
- [x] For pressure answers, dispatch geometry field by checking which of `answer.point/line/polygon` is not None
- [x] Include `geometry_id` in each feature's `properties`

## 7. Editor — Geometry Drawing Panel

- [x] Add `geometries_json` processing in `editor_question_create` and `editor_question_edit` in `survey/editor_views.py` — parse JSON and save to `question.geometries`
- [x] Add `geometries-editor` div and `geometries-json-input` hidden field to `question_form_modal.html` — show/hide based on `input_type == "pressure"` (same toggle pattern as `choices-editor`)
- [x] Add inline JS in `question_form_modal.html`: init Leaflet map in `#geometries-map`, add L.Draw controls, handle `draw:created` (generate UUID, add shape to list), serialize shapes on save
- [x] Add shape list UI in `#geometries-list` — each row has label input, color input, icon picker (reuse existing icon picker pattern), delete button
- [x] Load existing `question.geometries` into map and list when editing an existing pressure question
- [x] Add `"pressure"` to sub-question-enabled types in the editor (so "Add Sub-question" button appears for pressure questions)

## 8. Data Export

- [x] In `download_data` view, add pressure geometry type dispatch — check `answer.point/line/polygon` to determine geometry type and coordinates
- [x] Add `geometry_id` and `geometry_label` to GeoJSON feature properties for pressure answers (look up label from `question.geometries`)
- [x] Add pressure sub-question answers to CSV export — include `geometry_id` and `geometry_label` columns

## 9. Serialization

- [x] Add `"geometries": question.geometries` to `_serialize_question()` in `survey/serialization.py`
- [x] Add `"geometry_id": answer.geometry_id` to `_serialize_answer()` in `survey/serialization.py`
- [x] In question import, set `question.geometries = q_data.get("geometries")`
- [x] In answer import, set `answer.geometry_id = a_data.get("geometry_id")`

## 10. CSS

- [x] Add `.pressurebutton` styles (same base as `.drawbutton`) to survey CSS
- [x] Add `.pressure-shape-unanswered` (opacity 0.5) and `.pressure-shape-answered` (opacity 1.0) styles
- [x] Add `.pressure-answered-badge` style for checkmark overlay on answered point markers
- [x] Add `.geometries-editor` and `.geometry-row` styles for editor geometry panel

## 11. Tests

- [x] Model test: create Question with `input_type="pressure"` and `geometries` JSON, verify save/retrieve
- [x] Model test: create Answer with `geometry_id`, verify save/retrieve
- [x] Model test: verify `geo_questions()` includes pressure questions
- [x] View test: POST pipe-delimited GeoJSON with `geometry_id` in properties, verify Answer created with correct geo field and `geometry_id`
- [x] View test: GET section with existing pressure answers, verify `existing_geo_answers` includes them with `geometry_id`
- [x] View test: POST same `geometry_id` twice, verify upsert (single Answer updated, not duplicated)
- [x] Export test: export survey with pressure answers, verify GeoJSON contains `geometry_id` and `geometry_label`
- [x] Serialization test: export/import round-trip preserves `geometries` on Question and `geometry_id` on Answer
