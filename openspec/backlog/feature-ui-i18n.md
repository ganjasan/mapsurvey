# Translate UI buttons and instructions

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

Translate interface elements visible to survey respondents: "Next" button, "Draw polygon", "Draw line", "Draw point" instructions, and other UI text. Currently these are hardcoded in English even when the survey content is in another language.

## Notes

- Source: Manuel Frost (manu04) — his survey is in German but buttons and map instructions are in English
- Django i18n infrastructure exists, needs to be applied to survey-taking templates and Leaflet draw controls
- **2026-08-10 — CLOSED.** Respondent-facing chrome is translated: Next / Back / Finish in `survey/templates/survey_section_block.html:14,20,22`, draw and map strings via `survey/templatetags/i18n_extras.py:10-40`, and 75 compiled locales under `survey/locale/*/LC_MESSAGES/`. The survey's own language is activated per request (`survey/views.py:607,793`), so the chrome follows the survey rather than the browser.
