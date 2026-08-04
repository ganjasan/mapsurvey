# Number field exports as blank in CSV

**Type**: bug
**Priority**: medium
**Area**: backend
**Created**: 2026-03-30

## Description

A number-type question exports as a completely blank column in the CSV download, even though respondents submitted values. Reported by user bisq, who used the field for a district number. The data appears to be collected (the geopoint is present in the GeoJSON), but the number value is missing from the CSV.

## Notes

- Reported by: bisq (geography student conducting a city survey)
- Workaround: user derives the district from the geopoint coordinates in the GeoJSON export
- Need to investigate whether the issue is in answer storage or CSV serialization
- **2026-08-04**: two more defects found in the same export function while investigating a
  separate report — [datetime answers never exported](bug-datetime-missing-from-csv-export.md)
  and [GeoJSON sub-question property bleed](bug-geojson-subquestion-property-bleed.md). Both are
  now fixed in change `export-data-integrity`.
- **2026-08-04 — this item stays OPEN; it is not the same root cause.** The hypothesis that the
  property-bleed bug explained it was tested directly and refuted. Two tests written against the
  *unfixed* code both passed:
  - a `number` sub-question of a geo question, answered, reaches the feature's properties
  - a top-level `number` question, answered, reaches its CSV column as `7.0`
  So a number answer that exists is exported correctly, before and after the fix. Whatever happened
  to bisq's data lies elsewhere — most likely on the write path, not the read path. Both tests are
  in `ExportValueCorrectnessTest` and now serve as the reproduction this item previously lacked.
- Next step for this item is therefore the *save* path, not the export. Prime suspect: sub-answer
  storage branches on whether `sub_question.choices` is set rather than on `input_type`
  (`views.py:845-856`), so a question with leftover choices takes the wrong branch and can store
  nothing. Deliberately left out of `export-data-integrity`, which was scoped to the read path.
- Correction: an earlier version of this note said `download_data` has no test coverage. It had
  count-level and metadata-level tests; what was missing was value-level coverage.
