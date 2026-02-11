## Why

Currently the crosshair point-placement mechanism is only available on touch devices (`pointer: coarse`). Desktop users must use the less intuitive `L.Draw.Marker` click-to-place flow. Additionally, when a user taps/clicks an existing marker, the popup has an "Edit" button that enables vertex-dragging mode — but for point markers, dragging is awkward (especially on touch). There is no way to re-position a marker using the crosshair — the same precise, pan-to-place interface used for initial placement.

Unifying the crosshair UX across all device types and extending it to marker repositioning will make point placement consistent and easier on every device.

## What Changes

- **Remove the `isTouchDevice` gate** on crosshair mode: all devices (desktop and mobile) will use the crosshair overlay for point placement instead of `L.Draw.Marker`.
- **Add crosshair-based marker repositioning**: when the user clicks "Edit" in a point marker's popup, the system enters crosshair mode with the marker's current position pre-centered on the map. Pressing Apply moves the marker to the new map center; pressing Cancel restores the original position.
- **Adapt the info panel behavior**: on desktop the info panel already stays visible during crosshair mode; on mobile it slides away (existing behavior). No change needed here, but edit-mode crosshair must follow the same pattern.
- **Remove `L.Draw.Marker` usage for point questions entirely** — crosshair becomes the sole point-placement mechanism.

## Capabilities

### New Capabilities
- `crosshair-marker-edit`: Repositioning an existing point marker via the crosshair overlay (enter crosshair centered on marker, Apply/Cancel to confirm/discard new position)

### Modified Capabilities
- `mobile-point-crosshair`: Remove the touch-device-only restriction so crosshair mode is used for point placement on all devices (desktop and mobile)

## Impact

- **JS in `base_survey_template.html`**: `.drawpoint` click handler — remove `isTouchDevice` branch, always use `showCrosshair()`. `#draw_button` click handler — remove the `drawpoint` sub-branch from `start_draw` mode (no more `L.Draw.Marker` instantiation).
- **JS in `survey_section.html`**: `onPopupOpen` — the `layer-edit` button handler for point markers needs to enter crosshair-repositioning mode instead of calling `startEditMode(tempLayer)`.
- **CSS**: No new styles needed; existing crosshair overlay styles apply on all viewports.
- **Backend**: No changes — crosshair mode produces the same GeoJSON data format.
- **Existing specs affected**: `mobile-point-crosshair` (remove `pointer: coarse` requirement), `marker-draw-lifecycle` (crosshair now fires `draw:created` so single-shot behavior is preserved; edit flow does not use draw handler at all).
