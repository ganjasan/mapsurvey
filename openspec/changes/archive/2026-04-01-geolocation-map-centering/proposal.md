## Why

Survey maps always center on a fixed point (`SurveySection.start_map_postion`), which requires the survey creator to know the respondent's area in advance. For location-aware surveys — where the respondent should see their immediate surroundings — there is no way to auto-detect and center the map on the user's current position via browser geolocation.

## What Changes

- Add `use_geolocation` BooleanField to `SurveySection` (default `False`)
- When enabled, the survey map auto-centers on the respondent's browser location (zoom 13) on page load
- Add a "Locate me" button on the map for re-centering after the user pans away
- Show a blue dot circle marker at the user's position
- If geolocation is denied or fails, silently fall back to the configured `start_map_postion` and `start_map_zoom`
- Editor: checkbox toggle in section settings form
- Serialization: export/import the field
- Versioning: include in draft clone

## Capabilities

### New Capabilities
- `survey-geolocation`: Browser geolocation integration for survey maps — auto-center on respondent position, "Locate me" button, blue dot marker, graceful fallback

### Modified Capabilities
- `survey-editor`: Add `use_geolocation` toggle to section settings form
- `survey-serialization`: Export/import `use_geolocation` field on sections
- `survey-versioning`: Include `use_geolocation` in draft section clone
