## Why

Survey settings listed every base map as an inline row of checkboxes. A workspace can hold
hundreds of styles. The owner also noticed (2026-11-07) that the *Default position* map stayed on
Streets whatever *Default base map* said, so the creator framed the start on a map respondents
never see. The help text under *Base maps* named storage keys (`style:<uuid>`).

## What Changes

- *Base maps* folds into one line naming what is on ("Streets, Satellite, Topo +2"). A click opens
  the checklist, with a filter once there are more than eight base maps. One partial,
  `editor/partials/_basemap_picker.html`, serves the settings panel and the settings page.
- *Default base map* offers only the base maps that are on. A default that is switched off moves to
  the first one still on.
- The *Default position* map draws the default base map from the provider table and redraws when
  the default changes.
- The help text says what the control does, without keys.

## Capabilities

### New Capabilities

### Modified Capabilities
- `map-style-library`: the settings picker scales to many styles and the position map shows the default.

## Impact

`_basemap_picker.html` (new), `survey_settings_panel.html`, `survey_settings.html`,
`editor_forms.py` (help text), ten creator catalogs, one test. No model change.
