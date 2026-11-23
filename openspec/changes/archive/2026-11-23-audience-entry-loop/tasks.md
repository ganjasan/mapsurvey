## 1. Entry

- [x] 1.1 `visibility.respondent_entry_section(survey)`
- [x] 1.2 `survey_header`: render the nothing-to-fill page when sections exist and none is visible; otherwise redirect to the helper's section
- [x] 1.3 `survey_language_select` POST: redirect to the helper's section (nothing-to-fill page when None)
- [x] 1.4 Template `survey_no_public_pages.html` (respondent text + collaborator hint and editor link)

## 2. Editor

- [x] 2.1 `editor_survey_detail`: `no_public_pages` flag from the helper
- [x] 2.2 Banner in `editor/survey_detail.html`

## 3. Strings and tests

- [x] 3.1 New strings in every offered catalog (+ the respondent lines in `ru`)
- [x] 3.2 Tests in `survey/tests/test_question_audience.py`: skip, nothing-to-fill (no redirect, no session), direct section link ends, owner hint, multilingual, banner shown/absent
- [x] 3.3 Run the audience, routing and editor modules (full suite: the one failure is `ReportsCatalogTest`, untranslated Reports strings already on master)
