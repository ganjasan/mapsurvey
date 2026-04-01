# Geolocation Map Centering

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-01

## Description

Add a `use_geolocation` boolean flag on `SurveySection` so the map can auto-center on the respondent's current position via the browser Geolocation API. When enabled, the survey map requests the user's location on page load and re-centers accordingly. If permission is denied or the request fails, the map falls back to the configured `start_map_postion`.

## Notes

- Needed for a demo survey that shows the map at the respondent's location
- Blue dot marker to indicate "you are here"
- Touches: model, migration, frontend JS, editor form, serialization, versioning clone
- Plan details in `.claude/plans/refactored-honking-crayon.md`
