# Number field min/max validation

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

Allow survey creators to set min and max values on number-type questions. Currently respondents can enter any number — in the Lyon transit survey, someone entered 600 minutes for commute time (median is 5 min). Validation should reject out-of-range values on the frontend and backend.

## Notes

- Real case: Lyon transit survey (bisqunours), "Combien de temps mettez-vous" question — max answer 600 min with median 5 min
- Should be configurable per question in the editor (min, max fields)
- Display validation error inline, not as a page reload
- **2026-08-10 — partially shipped.** The creator can set min/max per question (`question_form_modal.html:107-125`, saved at `survey/editor_views.py:685`), but it only feeds post-hoc analytics linting (`survey/analytics.py:945-955`). Respondent input is still unvalidated: the number field is a bare `CharField`/`NumberInput` with no min/max attributes (`survey/forms.py:216-217`). Related: #107.
