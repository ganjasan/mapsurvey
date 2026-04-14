## Why

Survey maps reload from scratch on every section transition — tiles re-download, position resets, basemap resets. This creates poor UX for respondents navigating multi-section surveys: slow transitions, lost map context, jarring position jumps. Three users reported basemap resetting between sections, which exposed the deeper issue of full page reloads.

## What Changes

- Convert survey section navigation from full page reloads to HTMX-based partial swaps
- Map initializes once and persists across all sections — tiles cached, position/zoom/basemap preserved
- Section content (form, questions, navigation) swaps via HTMX without destroying the map
- Survey-level default map position, zoom, geolocation, and default basemap
- Section-level optional overrides: position/zoom (flyTo), basemap (switch), geolocation (locate user)
- Between sections: drawn features (editableLayers) cleared, previously saved answers restored

## Capabilities

### New Capabilities
- `persistent-map`: Leaflet map initialized once, survives section transitions
- `htmx-section-navigation`: Back/Next use HTMX partial swap instead of full page reload
- `survey-map-defaults`: Survey-level default position, zoom, geolocation, default basemap
- `section-map-overrides`: Optional per-section overrides for position, zoom, basemap, geolocation

### Modified Capabilities
- `survey-section-view`: Returns partial HTML for HTMX requests, full page for direct loads
- `draw-tools`: Event handlers become delegated, work across HTMX swaps
- `geo-answer-restore`: Runs after each HTMX swap via initSection()
- `event-tracking`: Beacons fire on HTMX swap events instead of page load/unload

## Impact

- **Templates**: Major refactor of `base_survey_template.html` (persistent shell) + new `partials/survey_section_partial.html`
- **Views**: `survey_section` split into full-page and HTMX-partial responses
- **Models**: SurveyHeader gets `default_basemap`, `start_map_position`, `start_map_zoom`; SurveySection fields become nullable + `override_basemap`
- **JS**: Draw handlers become delegated, new `initSection()` orchestrator, `switchBasemap()`
- **Editor**: Map picker and settings updated for new model fields
- **Serialization/Versioning**: New fields added
- **Migration**: 1 new migration (model changes)
