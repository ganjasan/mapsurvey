# datetime answers never appear in the CSV export

**Type**: bug
**Priority**: high
**Area**: backend
**Created**: 2026-08-04

## Description

`datetime` is an offered question type and its answers are stored correctly — the save path treats
it alongside text (`survey/views.py:702`, `question.input_type in ('text', 'text_line', 'datetime')`
→ value lands in `answer.text`). But the CSV export's elif chain only handles
`text`/`text_line`/`number`/`range`/`choice`/`rating`/`multichoice` and sends everything else to
`else: continue` (`survey/views.py:1171-1186`). A `datetime` answer is therefore collected, shown
in analytics, and silently dropped from the download.

The creator sees the question in the editor, sees answers in the responses table, and gets a CSV
with no such column — with no error to explain the gap.

## Notes

- Found 2026-08-04 while investigating Manuel Frost's export complaint.
- **2026-08-04 — FIXED** in change `export-data-integrity`, branch `fix/export-data-integrity`.
  `datetime` is exported as ISO 8601; values that do not parse pass through unchanged rather than
  being dropped.
- The `else: continue` that hid this is gone. Input types are now classified explicitly into
  value / geometry / display-only sets, and a type in none of them gets an empty column plus a
  logged warning. Raising was considered and rejected: one unrecognised question would deny every
  respondent's data.
- Related: [GeoJSON sub-question property bleed](bug-geojson-subquestion-property-bleed.md), fixed
  in the same change.
- Correction to an earlier note in this file's siblings: `download_data` was described as having no
  test coverage. It had count-level and metadata-level tests; the gap was value-level.
