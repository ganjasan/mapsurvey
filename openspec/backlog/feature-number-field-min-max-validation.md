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
