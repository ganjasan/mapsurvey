# Tasks: geometry-pressure-v2

## 1. Model & Migration

- [ ] Add `geometry = GeometryField(null=True, blank=True, srid=4326)` to Question model in `survey/models.py`
- [ ] Run `makemigrations` and verify the migration file
- [ ] Write data migration: for each Question with `input_type="pressure"` and non-empty `geometries` JSONField, create separate Questions per geometry entry (copy label→name, color, icon_class, geometry via GEOSGeometry), clone sub-questions for each new Question, set original's `geometries=None`

## 2. Form Layer — Respondent Side

- [ ] Update `_get_form_from_input_type()` in `survey/forms.py`: pressure returns a `CharField` with `HiddenInput` widget (`class="pressure-answer-input"`), not `PressureField`/`PressureButtonWidget`
- [ ] Remove or deprecate `PressureButtonWidget` and `PressureField` classes (no longer used)
- [ ] Remove `pressure_button.html` template (no longer used)

## 3. View — GET (Context for Respondent)

- [ ] In `survey_section` GET in `survey/views.py`, build `pressure_questions` list: for each question with `input_type="pressure"` and non-null `geometry`, serialize `code`, `name`, `subtext`, `color`, `icon_class`, `geometry.geojson`, `image.url`
- [ ] Pass `pressure_questions_json` (JSON-serialized) to template context
- [ ] Update `existing_geo_answers` for pressure: remove `geometry_id` from feature properties, each pressure question produces at most one feature keyed by question code

## 4. Respondent JavaScript

- [ ] In `base_survey_template.html` / `survey_section.html`: on map init, parse `pressure_questions_json`, create Leaflet layers (marker for Point, polyline for LineString, polygon for Polygon) in a non-editable `pressureLayerGroup`, set opacity 0.5
- [ ] Add click handler on each pressure layer: open popup with `subquestions_forms[questionCode]`, unique form ID per question code
- [ ] Add popup open/close handlers: populate form fields from `layer.feature.properties` on open, serialize back on close/apply
- [ ] Add visual feedback: track answered shapes in `pressureAnswered` Set, update opacity to 1.0 + checkmark on answered
- [ ] Add form submission handler: for each answered pressure question, serialize geometry + sub-question properties as GeoJSON, set hidden `pressure-answer-input` field value
- [ ] Add existing answer restoration: parse `existing_geo_answers` for pressure question codes, find matching pressure layers, copy properties, mark as answered

## 5. View — POST (Answer Saving)

- [ ] Update pressure POST handler in `survey_section` in `survey/views.py`: for each pressure question, check hidden input for data, parse JSON, upsert parent Answer (set geometry in point/line/polygon field from Question.geometry), create/update child Answers for sub-questions
- [ ] Remove `geometry_id` usage from new pressure answer saving logic

## 6. Editor — Section Map Editor (Backend)

- [ ] Add URL patterns in `survey/urls.py`: `editor_section_map_editor`, `editor_pressure_create`, `editor_pressure_update`, `editor_pressure_delete`, `editor_pressure_bulk_subquestion`, `editor_pressure_import`
- [ ] Implement `editor_section_map_editor` view (GET): render map editor template with `pressure_questions_json` for the section
- [ ] Implement `editor_pressure_create` view (POST): receive GeoJSON geometry + name/color/icon_class, create Question with `input_type="pressure"`, auto-assign order_number, return updated shape list partial
- [ ] Implement `editor_pressure_update` view (POST): update name/color/icon_class/geometry on existing pressure Question, return updated shape list item partial
- [ ] Implement `editor_pressure_delete` view (POST): delete pressure Question (cascade), return updated shape list partial
- [ ] Implement `editor_pressure_bulk_subquestion` view (POST): receive list of question IDs + sub-question definition, create sub-question for each selected Question, return updated shape list partial
- [ ] Implement `editor_pressure_import` view (POST): receive uploaded GeoJSON or KML file, parse features, create one Question per feature with geometry and mapped properties, return updated shape list partial

## 7. Editor — Section Map Editor (Frontend)

- [ ] Create template `editor/partials/section_map_editor.html`: fullscreen modal with Leaflet map (left) + shape list panel (right) + import/bulk action buttons
- [ ] Add Leaflet Draw controls (point, line, polygon) on the map editor, on `draw:created` POST to `editor_pressure_create` via HTMX
- [ ] Add shape list with checkboxes, inline edit fields (name, color, icon picker), edit/delete buttons per shape
- [ ] Add "Select All" / "Deselect All" toggle, selected count display
- [ ] Add bulk action buttons: "Add sub-question to selected" → opens sub-question form modal, on save POST to `editor_pressure_bulk_subquestion`; "Delete selected" → POST to `editor_pressure_delete` for each
- [ ] Add import button: file picker for GeoJSON/KML, on file select POST to `editor_pressure_import`
- [ ] Load existing pressure questions on editor open: render shapes on map and populate shape list

## 8. Editor — Question Modal Update

- [ ] Update `question_form_modal.html`: replace multi-shape geometries editor with single-geometry picker (small Leaflet map to draw ONE shape) when `input_type="pressure"`
- [ ] Update hidden input from `geometries_json` to `geometry_json` (single GeoJSON geometry object)
- [ ] Update `editor_question_create` and `editor_question_edit` in `editor_views.py`: parse `geometry_json`, convert to `GEOSGeometry`, save to `question.geometry`

## 9. Editor — Section Detail Integration

- [ ] Add "Map Editor" button to `section_detail_form.html` that opens the section map editor (HTMX GET to `editor_section_map_editor`)
- [ ] Add map editor modal container to the editor base template

## 10. Data Export

- [ ] Update `download_data` GeoJSON export: for pressure questions, add `shape_label` (from question.name) to feature properties instead of `geometry_id`/`geometry_label`
- [ ] Update `download_data` CSV export: include pressure sub-question answers with `question_code` and `question_name` columns

## 11. Serialization

- [ ] Update `_serialize_question()` in `survey/serialization.py`: add `"geometry": json.loads(question.geometry.geojson)` when geometry is not None
- [ ] Update question import: parse `geometry` field via `GEOSGeometry(json.dumps(geom_data), srid=4326)`
- [ ] Add backward compat: if imported question has `geometries` array (v1 format), expand into separate Questions
- [ ] Remove `geometry_id` from `_serialize_answer()` (deprecated)

## 12. CSS

- [ ] Add/update `.pressure-shape-unanswered` (opacity 0.5) and `.pressure-shape-answered` (opacity 1.0) styles
- [ ] Add section map editor styles: layout for map + shape list panel, shape row styling, bulk action bar
- [ ] Add single-geometry picker styles for question modal

## 13. Tests

- [ ] Model test: create Question with `input_type="pressure"` and `geometry=Point(...)`, verify save/retrieve
- [ ] Model test: verify `geo_questions()` includes pressure questions with geometry
- [ ] View test: POST pressure answer for a pressure Question, verify Answer created with correct geo field, no geometry_id
- [ ] View test: GET section with existing pressure answers, verify `existing_geo_answers` and `pressure_questions_json` in context
- [ ] View test: upsert — POST same pressure Question twice, verify single Answer updated
- [ ] Editor test: POST to `editor_pressure_create` with GeoJSON geometry, verify Question created
- [ ] Editor test: POST to `editor_pressure_import` with GeoJSON file, verify Questions created per feature
- [ ] Editor test: POST to `editor_pressure_bulk_subquestion`, verify sub-questions created for selected Questions
- [ ] Export test: export survey with pressure answers, verify GeoJSON contains `shape_label`
- [ ] Serialization test: export/import round-trip preserves `geometry` on Question
- [ ] Migration test: verify data migration converts v1 `geometries` JSONField to separate Questions
