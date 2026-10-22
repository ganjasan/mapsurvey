## Why

Respondents read the survey in one of 75 languages, but every interface string added since the
last bulk translation pass ships in English only: a Portuguese school survey shows "Show all
options", "Tap the map to mark a place — or use the button." and the safety footer in English to
pupils (#385). The only catalog guard (`TranslationCatalogHygieneTest`) checks creator surfaces in
the creator-offered languages, so nothing fails when a respondent string goes out untranslated —
epic #343 alone added four.

## What Changes

- Translate every interface msgid a respondent page looks up into all 75 catalogs in
  `survey/locale/` and compile them. Found today: `Show all options`, the tap-to-place hint,
  `%(n)s question(s)`, the abuse footer and report link, the spray tool controls
  (`Spray`, `Erase`, `Move map`), `A few required questions still need an answer.`, `Clear`,
  `Made with` / `create your own free map survey`, `See the results`, and whatever else the guard
  below finds on the same pages.
- Add a guard test that renders the respondent surfaces of a fixture survey covering every
  question type and display feature, records each msgid looked up through gettext while rendering,
  and fails when any of them is missing, empty or fuzzy in any catalog.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `ui-internationalization`: adds the requirement that respondent-facing interface strings are
  translated in every catalog, enforced by a test.

## Impact

- `survey/locale/*/LC_MESSAGES/django.po` and `.mo` (75 languages).
- `survey/tests.py`: new respondent catalog guard.
- No template, view or model change.
