# Finish Drawing Buttons for Polygon and Line

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-05

## Description

Add explicit "Close polygon" and "Finish line" buttons to Leaflet draw controls in survey forms. Currently there is no visible UI affordance for completing a polygon or line drawing — users must know to click the first point (polygon) or double-click (line), which is not discoverable.

## Notes

- Applies to survey respondent-facing map widgets (polygon and line question types)
- May also apply to the map picker in the editor
- **2026-08-10 — CLOSED.** A draw bar with **Finish drawing** and **Cancel** ships in `survey/templates/base_survey_template.html:89-92`, shown when a line or polygon draw starts (`:720-731`) and on edit (`:272-301`). Finish stays disabled until the minimum vertex count is reached (`:744-762`). The label is translated (`survey/templatetags/i18n_extras.py:18`).
