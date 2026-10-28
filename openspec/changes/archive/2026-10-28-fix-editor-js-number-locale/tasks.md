# Tasks: fix-editor-js-number-locale

## 1. Guard the four inline-JS blocks

- [x] 1.1 `editor/partials/section_map_picker.html`: `{% load l10n %}` + `{% localize off %}` around the inherit/section coordinate block
- [x] 1.2 `editor/partials/survey_settings_panel.html`: same around its lat/lng/zoom block
- [x] 1.3 `editor/survey_settings.html`: same
- [x] 1.4 `editor/partials/analytics_question_stats.html`: same around `minVal` / `maxVal`
- [x] 1.5 Leave the human-readable `floatformat` readouts localized — they are text for a person

## 2. Guard test

- [x] 2.1 Render each of the four templates under a comma-decimal locale with float coordinates and assert no digit-comma-digit sequence appears inside any `<script>` block
- [x] 2.2 Assert the same templates under `en` are unchanged, so the guard is not just asserting "no commas anywhere"
- [x] 2.3 Drive the real editor pages (settings, section modal) through the test client under that locale, not only the partials in isolation
- [x] 2.4 Put the page into the target language via the language COOKIE. `translation.override` is discarded by `LocaleMiddleware`, and `Accept-Language` loses to the cookie `login()` has already written — both were tried and both passed against the unfixed templates
- [x] 2.5 Use `de`, not `ru`: `ru` is no longer in `LANGUAGES` (only complete catalogs are listed), so a `ru` cookie silently falls back to English and the test asserts nothing
- [x] 2.6 Confirm the guard fails without the fix — 3 of 4 tests fail on the unpatched templates, reproducing `var lat = hasPosition ? 52,5231 : 52.52;`

## 3. Verification

- [x] 3.1 `./run_tests.sh survey` — compare against the 1761-test / OK baseline
- [ ] 3.2 After merge + deploy, mark PostHog issues `01a04d89`, `01a051a1`, `01a04d92` resolved
