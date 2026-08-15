# Tasks: Rating Question Display Style

## 1. Model & Migration

- [x] 1.1 Add `Question.display_style` CharField (choices `scale_strip`/`list_pips`, default `scale_strip`, max_length=20) in `survey/models.py`
- [x] 1.2 Create the additive migration (leaf after `0036_merge_20260723_0838`; re-check the leaf is still current before merging)

## 2. Respondent Rendering

- [x] 2.1 In `SurveySectionAnswerForm._get_form_from_input_type` rating branch, set `widget.display_style` from the question (keep plain `RadioSelect`; never touch `widget.input_type`)
- [x] 2.2 Add `rating_display_style` template filter next to the existing `question_type` filter
- [x] 2.3 Create `partials/rating_scale_strip.html`: numbered cells via `{% for radio in field %}` with `data-label`, inline `grid-template-columns: repeat(<n>, 1fr)`, anchors from first/last choice, empty chip container
- [x] 2.4 Create `partials/rating_list_pips.html`: full-width option rows with pip indicator (`forloop.counter` filled of total)
- [x] 2.5 Branch `survey_section_partial.html` card rendering on the filter to include the right partial for rating questions
- [x] 2.6 Replace `.question-card--rating` flex-wrap CSS in `survey/assets/css/main.css` with `.rating-scale-strip` and `.rating-list-pips` blocks per the mockup
- [x] 2.7 Add chip JS in `survey_section.html`: delegated `change` handler + on-load sync for pre-checked radio (back-navigation prepopulation)

## 3. Editor

- [x] 3.1 Add `display_style` to `QuestionForm` fields in `survey/editor_forms.py` (radio widget, labels "Compact scale" / "Labeled list")
- [x] 3.2 Add the "Display as" block with mini-previews to `question_form_modal.html`, toggled visible only for input_type `rating` by the existing type-toggle JS

## 4. Persistence Paths

- [x] 4.1 Export: add `display_style` to the question dict in `survey/serialization.py`
- [x] 4.2 Import: read `display_style` with validation against allowed values, fallback `scale_strip`
- [x] 4.3 Add `display_style=question.display_style` to `clone_question()` in `survey/cloning.py`

## 5. Tests & Verification

- [x] 5.1 Tests (GIVEN/WHEN/THEN): default on existing questions, scale-strip markup (cells, anchors, one row for 7 points), list-pips markup (rows, pips), prepopulated answer marks checked radio, submission stores choice code unchanged
- [x] 5.2 Tests: serialization export key, legacy-archive default, garbage-value fallback, round-trip; clone preserves style
- [x] 5.3 Test: editor form saves `display_style`; picker block present in modal template for rating
- [x] 5.4 Run `./run_tests.sh survey` (PostGIS container up), one baseline + one after-changes pass
- [x] 5.5 `collectstatic` and visually verify both styles + editor picker against `rating-question.mockup.html`

## 6. Modal Preview & Editor Fixes (после первой ревизии)

- [x] 6.1 `question_preview_frame.html`: rating-ветка через те же партиалы, что и survey_section_partial
- [x] 6.2 `editor_question_preview`: валидируемый `?display_style=` override для live-превью невыбранного стиля
- [x] 6.3 Modal JS: перезагрузка preview-iframe при переключении «Display as»
- [x] 6.4 Fix pre-existing бага: populate-блок choices перенести в конец IIFE (Apply и таблица choices при редактировании оживают)

## 7. Survey-level Default Style

- [x] 7.1 `SurveyHeader.style_settings` JSONField + helper `get_default_rating_display_style()`; `Question.display_style` → три значения, default `default`; миграция 0037 регенерируется
- [x] 7.2 Резолвинг эффективного стиля в `SurveySectionAnswerForm.__init__`
- [x] 7.3 Question modal picker: три опции (Survey default / Compact scale / Labeled list), fallback в clean → `default`
- [x] 7.4 Settings: секция Style в `SurveyHeaderForm` + `survey_settings.html` (радио дефолтного стиля)
- [x] 7.5 Serialization: export/import `style_settings` (+ `display_style` fallback → `default`); клонирование survey копирует `style_settings`
- [x] 7.6 Тесты: survey default применяется, per-question override побеждает, независимость вопросов, редактирование одного не трогает соседей, settings save, serialization roundtrip/fallback, preview override
- [x] 7.7 Полный прогон тестов + визуальная проверка в браузере
