## Why

Survey maps currently show only one basemap (Mapbox streets). Users working with nature/ecology (Galanthus — snowdrop mapping in rural Brittany), urban research (hmsbrito7 — children's affordances), and municipal planning need satellite imagery and topographic views to orient respondents in their environment. Three independent users have requested this feature.

## What Changes

- Add a per-survey setting to choose which basemaps are available to respondents
- Three basemap options: Streets (current Mapbox), Satellite (Esri World Imagery), Topographic (OpenTopoMap)
- Respondents see an L.control.layers switcher (top-right) when multiple basemaps are enabled
- Analytics maps also get the same layer control
- Editor survey settings page gets checkboxes to select available basemaps

## Capabilities

### New Capabilities
- `basemap-selection`: Per-survey multi-select of available basemap layers (streets, satellite, topo)
- `basemap-switcher`: L.control.layers UI for respondents and analytics to switch between enabled basemaps

### Modified Capabilities
- `survey-settings`: Add basemap checkboxes to editor settings page
- `survey-serialization`: Export/import basemaps field
- `survey-versioning`: Clone/publish basemaps field

## Impact

- **Models**: SurveyHeader — new `basemaps` JSONField
- **Templates**: New reusable partial `partials/basemap_layers.html`; 4 templates updated to use it
- **Editor**: survey_settings.html — checkbox picker; editor_forms.py, editor_views.py — wire field
- **Serialization**: serialization.py — export/import
- **Versioning**: versioning.py — clone/publish
- **Migration**: 1 new migration (AddField)
- **URLs**: No changes
