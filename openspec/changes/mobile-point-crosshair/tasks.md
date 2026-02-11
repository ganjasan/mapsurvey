## 1. Crosshair overlay HTML and CSS

- [x] 1.1 Add `#crosshair-overlay` HTML to `base_survey_template.html` — SVG pin marker (teardrop path) with FA icon inside, rectangular Cancel/Apply buttons with text labels. Hidden by default (`display: none`).
- [x] 1.2 Add CSS for `#crosshair-overlay` in `main.css` — full-screen overlay with centered pin, action buttons fixed at bottom of screen, rectangular with rounded corners (8px), min 48px height, `pointer-events: none` on overlay / `auto` on buttons.

## 2. Touch detection and crosshair mode activation

- [x] 2.1 Add `isTouchDevice` variable in `base_survey_template.html` JS using `window.matchMedia('(pointer: coarse)').matches`
- [x] 2.2 Modify `.drawpoint` click handler — if `isTouchDevice`, show crosshair overlay with the question's icon/color (from button's `data-icon` and `data-color`) and set `currentQ`, instead of creating `L.Draw.Marker`

## 3. Apply and Cancel actions

- [x] 3.1 Implement Apply button click handler — read `map.getCenter()`, create `L.marker` with question icon/color, set `feature.properties.question_id`, bind sub-question popup (reuse existing popup template from `draw:created` handler), add to `editableLayers`, hide overlay. Open popup if sub-questions exist, otherwise call `endDrawMode()`.
- [x] 3.2 Implement Cancel button click handler — hide crosshair overlay, show info panel (`toggleInfo(true)`), reset `currentQ`

## 4. Info panel improvements

- [x] 4.1 Mobile info panel partial width (85%) — no longer covers 100% of screen
- [x] 4.2 Slide animation for info panel show/hide — CSS `transform: translateX()` with 0.3s ease transition, replaces `visibility` toggle
- [x] 4.3 `toggleInfo()` uses CSS class `.hidden` instead of `visibility` style

## 5. Testing

- [ ] 5.1 Manual test on a touchscreen device (or Chrome DevTools touch emulation) — verify pin-shaped crosshair appears, map pans under it, Apply places marker correctly, Cancel returns to info panel
- [ ] 5.2 Manual test on desktop with mouse — verify standard `L.Draw.Marker` flow is unchanged
- [ ] 5.3 Verify placed markers serialize correctly on form submit — same GeoJSON format in hidden input as standard flow
- [ ] 5.4 Verify info panel slide animation works on mobile — slides in/out smoothly, shows map edge when visible
