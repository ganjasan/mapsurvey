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
- Fix: handle `datetime` in the export chain, reading `answer.text`. Decide the serialised format
  explicitly (ISO 8601 is the safe default for a file that gets opened in Excel and QGIS).
- While in this function, audit the `else: continue` branch for every value in `INPUT_TYPE_CHOICES`
  — the same silent-drop shape applies to any type added later. Consider failing loudly (or
  emitting an empty column) for unhandled types instead of skipping.
- Related: [GeoJSON sub-question property bleed](bug-geojson-subquestion-property-bleed.md),
  [Number field blank in CSV export](bug-number-field-blank-in-csv-export.md) (#23).
