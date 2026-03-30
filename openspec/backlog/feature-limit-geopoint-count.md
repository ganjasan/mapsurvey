# Limit geopoint count per question

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-03-30

## Description

Allow survey creators to set a maximum number of geopoints a respondent can place on the map for a given question. Currently users can place unlimited points, lines, or polygons. Adding a configurable limit (e.g., "max 1 point") would give creators more control over responses.

## Notes

- Requested by: bisq (geography student)
- Should apply to all geo question types (point, line, polygon)
- Could be a `max_features` field on Question model, with null/0 meaning unlimited
- Frontend Leaflet draw widget would need to enforce the limit (disable draw control when max reached)
