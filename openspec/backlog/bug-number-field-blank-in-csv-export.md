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
