# Rework response Warnings/Violations: hints, not errors

**Type**: improvement
**Priority**: high
**Area**: frontend
**Epic**: data-management
**Created**: 2026-09-07

## Description

The answer lints on the Responses page (`compute_answer_lints`, the Violations panel, the
yellow/red cell icons) read as errors to creators. A thesis user (marta25, PPGIS Húnaflói Bay)
asked whether she can still download data that carries "warning signs". Nothing on the page says
the hints are advisory and that nothing is excluded from the data or export.

Rework the presentation so a hint is unmistakably a hint, and the geo cell shows what the hint
is about.

## Notes

What is wrong today (2026-09-07 audit):

- **Polygons are flagged by one rule only: `area_outlier`** — area >10× or <1/10 of the
  per-question median, fires on any question with ≥3 polygons. In participatory mapping a
  100× size spread is legitimate (one respondent draws a cove, another the whole bay), so a
  large share of honest polygons get a triangle.
- **The icon sits next to a cell that is about something else.** Geo cells render as
  "N vertices" (`_format_cell`, `survey/analytics.py`), so the table shows "⚠ 7 vertices" and
  the reader concludes the vertex count is the problem. The tooltip explains area, but nobody
  hovers. Lines carry the same "N vertices" text and are never linted at all.
- **Error styling**: yellow cell fill + border + `fa-exclamation-triangle`; red circle for
  errors. The panel is titled "Violations". Tooltip texts are judgmental ("suspiciously
  short", "much larger or smaller than typical").
- **No off switch.** Thresholds live in `Question.validation_settings`
  (`area_outlier_factor`, `min_length`, `outlier_sigma`) but no UI edits them and hints cannot
  be hidden. Filter "Has answer warnings" exists; "hide hints" does not.
- **`self_intersection` is caught after submission, not at draw time**: the polygon widget
  does not set `allowIntersection: false`, so respondents draw figure-eights and creators get a
  red error they cannot act on.
- "Doesn't record the time" from the same user is probably the missing end-time column
  (memory `lesson_end_datetime_never_set`); the `fast` rule works off `SurveyEvent`, not the
  session field.

Proposed minimum:

1. Rename "Violations"/"Warnings" → "Hints"; neutral icon, drop the cell fill.
2. One line in the panel: "Hints flag unusual answers. Nothing is excluded from your data or
   export."
3. Factual tooltip texts with the number: "Area is 14× the median for this question".
4. Geo cells show area (km²) / length (km) instead of "N vertices", so the area hint lands on
   a visible number.
5. "Show hints" toggle on the Responses page, remembered in `localStorage`.
6. Separately: `allowIntersection: false` in the polygon draw widget, removing the
   self-intersection error as a class.

Source: marta25 emails 2026-09-04 and 2026-09-07
(`docs/marketing/user-outreach/marta25/correspondence/`).
