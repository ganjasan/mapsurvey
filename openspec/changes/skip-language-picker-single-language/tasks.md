# Tasks — skip-language-picker-single-language

## 1. Implementation

- [x] 1.1 `is_multilingual()` → `len(available_languages) > 1`
- [x] 1.2 `survey_section`: when the session has no `survey_language` but the
      survey has languages, default `selected_language` to
      `available_languages[0]` and store it in session (single-language surveys)

## 2. Verification

- [x] 2.1 Test: a one-language survey entry (`survey_header`) redirects straight
      to the first section, not the language picker
- [x] 2.2 Test: a one-language survey section renders and creates a
      `SurveySession` whose `language` is that single language
- [x] 2.3 Test: a two-language survey still redirects to the picker
- [x] 2.4 Full `./run_tests.sh survey` green
