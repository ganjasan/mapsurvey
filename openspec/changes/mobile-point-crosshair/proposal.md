## Why

On touchscreen devices, placing a point marker on the survey map is confusing and frustrating. When a user taps the map to place a marker, the info panel (question list) covers the entire screen, blocking the map view. There is no visual guidance on where the marker will be placed. Users don't know what to do. This affects phones, tablets, and any device where the primary pointer is a finger.

## What Changes

- Add a **crosshair mode** for point placement on touchscreen devices: a fixed crosshair icon displayed at the center of the map screen. The user pans the map to position the crosshair over the desired location, then confirms or cancels.
- Show two action buttons below the crosshair: **Cancel** (red X) and **Apply** (green checkmark).
- **Apply** places the marker at the crosshair's map position and exits crosshair mode.
- **Cancel** discards the placement and exits crosshair mode.
- The info panel is hidden while crosshair mode is active, giving the user a full-screen map view.
- **Touch detection**: use `window.matchMedia('(pointer: coarse)')` to detect that the primary pointing device is a finger (coarse pointer). This correctly targets phones, tablets, and touch-only devices while leaving mouse/trackpad users on the standard `L.Draw.Marker` flow.
- Applies only to `point` type questions. Line and polygon drawing remain unchanged.

## Capabilities

### New Capabilities
- `mobile-point-crosshair`: Crosshair-based point placement UX for touchscreen devices — fixed center marker, pan-to-position, confirm/cancel buttons, coarse-pointer detection.

### Modified Capabilities

_(none — this is a new UI mode layered on top of existing point input, no spec-level changes to existing capabilities)_

## Impact

- **Templates**: `base_survey_template.html` — new crosshair overlay HTML and JS logic for mobile draw mode
- **CSS**: `survey/assets/css/main.css` — crosshair element styling, action button styling
- **JS**: Inline script in `base_survey_template.html` — detect `pointer: coarse`, intercept `.drawpoint` click on touch devices, enter crosshair mode instead of `L.Draw.Marker`, read map center on Apply
- **No backend changes**: point data format (GeoJSON in hidden input) stays the same
- **No model changes**: no migrations needed
