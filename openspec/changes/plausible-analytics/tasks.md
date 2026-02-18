## 1. Settings and Context Processor

- [x] 1.1 Add `PLAUSIBLE_DOMAIN` and `PLAUSIBLE_SCRIPT_URL` to `mapsurvey/settings.py`
- [x] 1.2 Add `analytics()` context processor to `survey/context_processors.py`
- [x] 1.3 Register `survey.context_processors.analytics` in `TEMPLATES` config in `settings.py`

## 2. Analytics Template Partial

- [x] 2.1 Create `survey/templates/partials/_analytics.html` with conditional Plausible script tag

## 3. Base Template Integration

- [x] 3.1 Remove Yandex Metrica from `base_survey_template.html` and add analytics include
- [x] 3.2 Add analytics include to `base.html`
- [x] 3.3 Add analytics include to `base_landing.html`
- [x] 3.4 Add analytics include to `editor/editor_base.html`

## 4. Custom Funnel Events

- [x] 4.1 Add `survey_start` and `survey_section_complete` event scripts to `survey_section.html`
- [x] 4.2 Add `survey_complete` event script to `survey_thanks.html`

## 5. Tests

- [x] 5.1 Test: no Plausible script when `PLAUSIBLE_DOMAIN` is unset
- [x] 5.2 Test: Plausible script present when `PLAUSIBLE_DOMAIN` is set
- [x] 5.3 Test: Yandex Metrica code is absent from all pages
- [x] 5.4 Test: custom event scripts present on survey section and thanks pages
