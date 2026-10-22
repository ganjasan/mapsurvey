## 1. Guard first

- [x] 1.1 Fixture survey in `survey/tests.py` covering the design's feature list (two languages, map section with every geo type, tap-to-place point with icon-grid choice, collapsible group and thumbs in its pop-up, form section with choice/multichoice/rating/number/text and one required question)
- [x] 1.2 `RespondentCatalogTest`: record msgids looked up through `translation._trans` (gettext, ngettext, pgettext, npgettext) while an anonymous client renders the language choice, every section, an empty POST of the required question, the thanks page and the report form
- [x] 1.3 Assert each recorded msgid of ours (named in any `survey/locale` `.po`, or written in our source) is translated in every compiled `.mo` but `en`; failure message lists msgid → missing languages
- [x] 1.4 Run the test on the unchanged catalogs and record the failing msgids (baseline)

## 2. Translations

- [x] 2.1 Add or fill every baseline msgid in all 75 `django.po` files, placeholders and plural forms intact, no fuzzy flags
- [x] 2.2 `msgfmt --check` every catalog and compile the `.mo` files
- [x] 2.3 Respondent catalog test passes; `TranslationCatalogHygieneTest` still passes

## 3. Verify

- [x] 3.1 Open a Portuguese section with icon grid and tap-to-place in a browser: grid control, tap hint, footer and report link in Portuguese
- [x] 3.2 Full `./run_tests.sh survey` once — 2758 tests, 1 failure already on master (`HtmxPromiseGuardTest`, `editor/survey_detail.html:900`, a file this change does not touch)
