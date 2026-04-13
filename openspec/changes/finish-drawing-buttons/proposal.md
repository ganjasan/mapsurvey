## Why

When survey respondents draw polygons or lines on the map, there is no visible UI button to complete or cancel the drawing. Users must know to click the first point (polygon) or double-click (line) to finish — this is not discoverable for non-technical respondents. Point placement already has visible Cancel/Apply buttons via the crosshair overlay, but polygon/line drawing lacks equivalent affordance.

Additionally, the existing edit-mode "Finish editing" button sits at `top: 5%` in `#drawbar`, inconsistent with the bottom-fixed crosshair pattern.

## What Changes

- Add a bottom-fixed action bar with "Cancel" and "Finish drawing" buttons that appears during polygon/line drawing
- "Finish drawing" is disabled until minimum vertices are placed (3 for polygon, 2 for line)
- Repurpose `#drawbar` from top-positioned single button to bottom-fixed action bar
- Edit mode reuses the same bar with "Finish editing" label
- Remove dead code: unused `startDrawMode()`, old `#draw_button` state machine

## Capabilities

### New Capabilities
- `finish-drawing-buttons`: Visible Cancel/Finish action bar during polygon and line drawing on survey maps

### Modified Capabilities
- `edit-mode-bar`: Edit-mode finish button moved from top to bottom-fixed position for consistency

## Impact

- **Templates**: `base_survey_template.html` — new drawbar HTML, updated JS handlers
- **CSS**: `main.css` — restyle `#drawbar` to bottom-fixed, add button styles
- **i18n**: `i18n_extras.py` — add `finishDrawing` and `cancel` translation keys
- **Models**: No changes
- **URLs**: No changes
