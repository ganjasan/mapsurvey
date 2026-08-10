# Hide language picker when survey has only one language

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-14

## Description

When a survey has only one language configured in `available_languages`, the language selection bar should not be displayed to respondents. It adds unnecessary UI clutter and confusion when there is nothing to choose from.

## Notes

- Affects the public survey view (`survey_section.html`)
- Condition: hide when `available_languages` has 0 or 1 entries
- **2026-08-10 — CLOSED.** `SurveyHeader.is_multilingual()` requires more than one language (`survey/models.py:432`); the picker is skipped (`survey/views.py:596-599`) and the entry redirect is gated on it (`:658-660`). Covered by `survey/tests.py:3153,3164`.
