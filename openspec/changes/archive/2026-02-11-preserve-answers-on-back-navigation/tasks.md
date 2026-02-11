## 1. Backend: Build initial values from existing answers

- [x] 1.1 In `survey_section` GET handler, query Answer records for the current session and section's questions (top-level only, `parent_answer_id=None`)
- [x] 1.2 Build `initial` dict from scalar answers: map `question.code` to the saved value — `text` for text/text_line/datetime, `numeric` for number/range, `str(selected_choices[0])` for choice/rating, `[str(c) for c in selected_choices]` for multichoice
- [x] 1.3 Pass `initial` dict to `SurveySectionAnswerForm` instead of `initial={}`

## 2. Backend: Build geo answer GeoJSON for template

- [x] 2.1 For each geo question with saved answers, convert Answer geometry to GeoJSON Feature with `properties.question_id` set to `question.code`
- [x] 2.2 For each geo Answer, query child Answers (`parent_answer_id=answer`) and add sub-question values to feature properties in `{sub_question.code: [value]}` format
- [x] 2.3 Build `existing_geo_answers` dict keyed by question code, JSON-serialize it, and pass to template context

## 3. Frontend: Restore geo features on map load

- [x] 3.1 In `survey_section.html` or `base_survey_template.html`, parse `existing_geo_answers` JSON on page load
- [x] 3.2 For each feature, create the appropriate editable Leaflet layer (L.marker for point, L.polyline for line, L.polygon for polygon), set `feature.properties`, and add to `editableLayers`
- [x] 3.3 Bind sub-question popup to each restored layer using the same popup HTML from `subquestions_forms` (existing `onPopupOpen` logic reads properties automatically)

## 4. Backend: Delete existing answers on re-submission

- [x] 4.1 In `survey_section` POST handler, before saving new answers, delete all existing Answer records for the current session and section's questions (child answers cascade via `parent_answer_id`)

## 5. Tests

- [x] 5.1 Test: scalar field prepopulation — submit a section, GET the same section, verify form initial values contain saved answers
- [x] 5.2 Test: geo answer restoration — submit a section with geo answers, GET the same section, verify `existing_geo_answers` context contains correct GeoJSON
- [x] 5.3 Test: re-submission replaces answers — submit a section twice with different values, verify only the latest answers exist
- [x] 5.4 Test: first visit shows empty form — visit a section with no saved answers, verify `initial` is empty and no geo answers in context
