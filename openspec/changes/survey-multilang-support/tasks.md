## 1. Translation Models

- [x] 1.1 Add `available_languages` JSONField to `SurveyHeader` model
- [x] 1.2 Add `language` CharField (nullable) to `SurveySession` model
- [x] 1.3 Create `SurveySectionTranslation` model (FK to SurveySection, language, title, subheading)
- [x] 1.4 Create `QuestionTranslation` model (FK to Question, language, name, subtext)
- [x] 1.5 Create `OptionChoiceTranslation` model (FK to OptionChoice, language, name)
- [x] 1.6 Add `get_translated_title(lang)` and `get_translated_subheading(lang)` to `SurveySection`
- [x] 1.7 Add `get_translated_name(lang)` and `get_translated_subtext(lang)` to `Question`
- [x] 1.8 Add `get_translated_name(lang)` to `OptionChoice`
- [x] 1.9 Add `is_multilingual()` property to `SurveyHeader`
- [x] 1.10 Create and apply database migration
- [x] 1.11 Write tests for translation models and helper methods

## 2. Admin Interface

- [x] 2.1 Create `SurveySectionTranslationInline` for `SurveySectionAdmin`
- [x] 2.2 Create `QuestionTranslationInline` for `QuestionAdmin`
- [x] 2.3 Create `OptionChoiceTranslationInline` for `OptionChoiceAdmin`
- [x] 2.4 Add `available_languages` field to `SurveyHeaderAdmin`
- [x] 2.5 Write tests for admin inlines (translation creation via admin)

## 3. Language Selection

- [x] 3.1 Create `survey_language_select` view function
- [x] 3.2 Create `survey_language_select.html` template with language buttons
- [x] 3.3 Add URL pattern `/surveys/<survey_name>/language/`
- [x] 3.4 Activate Django i18n language on selection and store in Django session
- [x] 3.5 Store selected language in `SurveySession.language`
- [x] 3.6 Write tests for language selection view

## 4. Survey Flow Integration

- [x] 4.1 Modify `survey_header` view to redirect to language selection for multilingual surveys
- [x] 4.2 Modify `survey_section` view to check for language selection and redirect if missing
- [x] 4.3 Pass selected language to template context in `survey_section` view
- [x] 4.4 Write tests for survey flow redirects (multilingual and single-language)

## 5. Translated Content Display

- [x] 5.1 Modify `SurveySectionAnswerForm` to accept `language` parameter
- [x] 5.2 Use translated question names and subtexts in form field generation
- [x] 5.3 Use translated option choice names in choice fields
- [x] 5.4 Update `survey_section.html` to display translated section title and subheading
- [x] 5.5 Write tests for form field labels with translations

## 6. Serialization

- [ ] 6.1 Add `available_languages` to survey.json export in `export_survey_to_zip`
- [ ] 6.2 Add `translations` array to section, question, and option choice serialization
- [ ] 6.3 Add `language` field to session serialization in responses.json
- [ ] 6.4 Import `available_languages` field in `import_survey_from_zip`
- [ ] 6.5 Import translations for sections, questions, and option choices
- [ ] 6.6 Import session `language` field from responses.json
- [ ] 6.7 Write tests for export/import round-trip with translations

## 7. Integration Testing

- [ ] 7.1 Write end-to-end test: create multilingual survey, select language, complete survey
- [ ] 7.2 Write test: export multilingual survey, import to fresh DB, verify translations
- [ ] 7.3 Write test: single-language survey backwards compatibility (no language screen)
- [ ] 7.4 Write test: missing translation falls back to original content
