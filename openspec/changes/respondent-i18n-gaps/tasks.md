## 1. Guard test first (red)

- [x] 1.1 Add `RespondentCatalogCompletenessTest` to `survey/tests.py`: `RESPONDENT_SOURCES` tuple, template msgids via `templatize`, Python msgids via `ast`, every non-`en` locale must have a non-empty, non-fuzzy msgstr
- [x] 1.2 Add the include-graph assertion: every template `{% include %}`d from the survey page and respondent pages is in `RESPONDENT_SOURCES`
- [x] 1.3 Run it and confirm it fails on today's catalogs, naming "Please specify" and the empty `ar`/`fa`/`he`/`ur` catalogs

## 2. Mark hard-coded English for translation

- [x] 2.1 `survey_thanks.html`: replace the ru/ky/en share dict with `{% trans %}` strings
- [x] 2.2 Map controls: zoom in/out, "Locate me" and the layers toggle title from `i18n_extras`; basemap names in `partials/basemap_layers.html`
- [x] 2.3 `choice_dropdown.html` search placeholder; `ranking.html` hint and empty-state text
- [x] 2.4 `ranking.js` live-region announcements via `data-msg-*` on the ranking root
- [x] 2.5 `file_upload.html` sets `data-msg-too-large`, `data-msg-required`, `data-msg-failed`, `data-msg-remove`; `file_upload.js` reads them for every message it builds
- [x] 2.6 `views.py` password gate error and `content_screening.REPORT_REASONS` wrapped in gettext (lazy for the module constant)
- [x] 2.7 `public_results.html` "Answers" header and the spray-grid caption

## 3. Survey language on every respondent page

- [x] 3.1 Add `activate_survey_language(request, survey)` with the session → browser-if-offered → first-language order; never writes the language cookie
- [x] 3.2 Call it from thanks (before the session pop), password gate, closed/unavailable renders in `check_survey_access`, the report views and the upload endpoint
- [x] 3.3 Tests for every scenario in `specs/survey-language-selection/spec.md`, including the editor-language isolation one

## 4. Catalogs

- [x] 4.1 Add missing respondent msgids to all 74 catalogs textually (no `makemessages` — see design §4); replace the two wrong fuzzy `ky` guesses
- [x] 4.2 Produce translations for every respondent msgid missing in each locale (incl. the 31 base strings for `ar`/`fa`/`he`/`ur`), merge with polib
- [x] 4.3 `compilemessages`; run `TranslationCatalogHygieneTest` and the new completeness test green
- [ ] 4.4 Owner spot-reads `pl`, `de`, `ru` respondent strings (owner chose to merge first and correct from feedback)

## 5. Verify

- [x] 5.1 Full `./run_tests.sh survey` once after changes; compare with the baseline
- [x] 5.2 Browser check: a Polish survey with an English browser — "Other" write-in, spray panel, map control titles, thanks page, password gate
- [x] 5.3 PR referencing #285
