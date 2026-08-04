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
  and [GeoJSON sub-question property bleed](bug-geojson-subquestion-property-bleed.md). Since
  bisq's number lived in a sub-question of a geo question, the property-bleed bug is a plausible
  root cause for this one too. `download_data` has no test coverage; fix the three together and
  cover the whole function rather than patching each symptom.
