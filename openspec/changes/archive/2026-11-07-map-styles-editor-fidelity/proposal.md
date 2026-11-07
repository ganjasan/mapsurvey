## Why

The owner opened a copy of Streets in the style editor and saw a different map online than on the
Print tab (epic #545). The controls had no "leave the base alone" state: Streets' settings document
is empty, but the form filled every control with Paper-A-like defaults (white land, grey roads, label
colours, place names cut at zoom 12), so the preview and every Save repainted Streets. In the same
session the owner asked for three things the editor lacked: clicking a colour code should open a
colour picker, buildings should be shown from a zoom the creator picks, and the preview needs a
place search.

## What Changes

- Every control gets a base state: a colour left empty shows the colour the base really draws (read from the base style by `controls.base_colours`, muted; ↺ returns to it), roads
  "As base", place names "no limit" (17), buildings at the base's zoom (15). A control in its base
  state adds no key, so an untouched style saves the document it had. Road triples that match no
  preset (Paper B, imports) show as a checked "Custom" option and are kept.
- The colour code is a native colour picker (`<input type="color">` under the code).
- Buildings get a "Show buildings from zoom" slider (13–17) written as `buildings.minzoom`;
  fill and outline colours a style already has are kept.
- The place-dot icons are removed only when label colours are set (they were dropped from Streets).
- The preview bar carries the shared place search (`js/components/map_place_search.js`, through a
  small MapLibre adapter); a chosen place moves the preview and the Print frame until another survey
  frame is picked.

## Capabilities

### New Capabilities

### Modified Capabilities
- `map-style-editor`: base-state controls, colour picker, buildings zoom, Custom roads, place search.

## Impact

`survey/map_styles/controls.py`, `survey/map_styles/generator.py`, `org/map_style_editor.html`,
`js/map_style_editor.js`, `css/map_style_editor.css`, the editor view's i18n state, ten creator
catalogs, `survey/tests/test_map_style_editor.py`. No model or migration.
