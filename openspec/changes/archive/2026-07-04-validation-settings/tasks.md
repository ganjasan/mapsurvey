## 1. Model

- [ ] 1.1 Add `validation_settings` JSONField (default=dict, blank=True) to SurveyHeader
- [ ] 1.2 Add `validation_settings` JSONField (default=dict, blank=True) to Question
- [ ] 1.3 Create migration 0026

## 2. Service integration

- [ ] 2.1 `compute_session_issues()` reads survey.validation_settings for fast_threshold_seconds, duplicate_window_hours
- [ ] 2.2 `compute_answer_lints()` reads survey.validation_settings for short_text_min_chars, area_outlier_factor, numeric_outlier_sigma
- [ ] 2.3 `compute_answer_lints()` reads question.validation_settings for min_value, max_value, min_length

## 3. Survey settings UI

- [ ] 3.1 Add `analytics_validation_settings` GET/POST endpoint (returns/saves survey validation_settings)
- [ ] 3.2 Add URL pattern
- [ ] 3.3 Add settings modal in analytics dashboard with form fields for all survey-level thresholds
- [ ] 3.4 JS to open/save settings modal

## 4. Question editor integration

- [ ] 4.1 Add validation_settings fields to question edit form in editor (min_value, max_value for number; min_length for text)
- [ ] 4.2 Save validation_settings in editor_question_edit view

## 5. Tests

- [ ] 5.1 Test custom fast_threshold_seconds changes detection threshold
- [ ] 5.2 Test question min_value/max_value creates lint errors
- [ ] 5.3 Test settings endpoint saves and returns settings
