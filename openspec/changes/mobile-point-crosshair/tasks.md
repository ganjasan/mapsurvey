## 1. Crosshair overlay HTML and CSS

- [x] 1.1 Add `#crosshair-overlay` HTML to `base_survey_template.html` — container div with crosshair icon element, Cancel button (red, `fa-times`), and Apply button (green, `fa-check`). Hidden by default (`display: none`).
- [x] 1.2 Add CSS for `#crosshair-overlay` in `main.css` — `position: fixed`, centered via `top: 50%; left: 50%; transform: translate(-50%, -50%)`, `z-index: 15`, `pointer-events: none`. Action buttons get `pointer-events: auto` and min 44x44px touch targets.

## 2. Touch detection and crosshair mode activation

- [x] 2.1 Add `isTouchDevice` variable in `base_survey_template.html` JS using `window.matchMedia('(pointer: coarse)').matches`
- [x] 2.2 Modify `.drawpoint` click handler — if `isTouchDevice`, show crosshair overlay with the question's icon/color (from button's `data-icon` and `data-color`) and set `currentQ`, instead of creating `L.Draw.Marker`

## 3. Apply and Cancel actions

- [x] 3.1 Implement Apply button click handler — read `map.getCenter()`, create `L.marker` with question icon/color, set `feature.properties.question_id`, bind sub-question popup (reuse existing popup template from `draw:created` handler), add to `editableLayers`, hide overlay. Open popup if sub-questions exist, otherwise call `endDrawMode()`.
- [x] 3.2 Implement Cancel button click handler — hide crosshair overlay, show info panel (`toggleInfo(true)`), reset `currentQ`

## 4. Testing

- [ ] 4.1 Manual test on a touchscreen device (or Chrome DevTools touch emulation) — verify crosshair appears, map pans under it, Apply places marker correctly, Cancel returns to info panel
- [ ] 4.2 Manual test on desktop with mouse — verify standard `L.Draw.Marker` flow is unchanged
- [ ] 4.3 Verify placed markers serialize correctly on form submit — same GeoJSON format in hidden input as standard flow
