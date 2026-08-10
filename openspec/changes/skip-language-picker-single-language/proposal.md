# Skip the language picker for single-language surveys

## Why

`SurveyHeader.is_multilingual()` returned `True` whenever `available_languages`
had **at least one** entry (`len > 0`). A survey configured with exactly one
language therefore showed respondents a language-selection screen with a single
option — a pointless click. The spec already says the picker is for surveys with
*multiple* languages; the implementation was the bug ("Если выбран только один
язык, то незачем при старте опроса просить выбрать язык" — user, 2026-07-04).

## What Changes

- `is_multilingual()` returns `True` only when **more than one** language is
  configured (`len > 1`). Zero- and one-language surveys skip the picker and go
  straight to the first section.
- A one-language survey auto-selects that language for content and the session:
  `survey_section` defaults `selected_language` to `available_languages[0]` when
  the session has none, so content renders in the survey's language (not the
  fallback) and the `SurveySession.language` is recorded.
- Bonus: the analytics dashboard's per-language chart (`_stats_language`) now
  only appears for genuinely multilingual surveys, not as a useless single bar.

## Impact

- Affected specs: `survey-language-selection`
- Affected code: `survey/models.py` (`is_multilingual`), `survey/views.py`
  (`survey_section` language default); no migration.
