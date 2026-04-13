## 1. i18n

- [ ] 1.1 Add `finishDrawing` and `cancel` keys to `i18n_extras.py`

## 2. HTML — Replace drawbar

- [ ] 2.1 Replace `#drawbar` HTML in `base_survey_template.html`: two buttons (Cancel + Finish) instead of single `#draw_button`
- [ ] 2.2 Finish button gets `disabled` attribute by default

## 3. CSS — Restyle drawbar

- [ ] 3.1 Restyle `#drawbar` in `main.css`: `position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%)`
- [ ] 3.2 Style Cancel and Finish buttons matching crosshair-cancel/crosshair-apply visual pattern

## 4. JS — Draw mode wiring

- [ ] 4.1 Update `.drawpolygon` click handler: show drawbar, store draw type context
- [ ] 4.2 Update `.drawline` click handler: show drawbar, store draw type context
- [ ] 4.3 Add `map.on('draw:drawvertex')` listener: count vertices, enable Finish when >= minimum (3 polygon, 2 line)
- [ ] 4.4 Wire Cancel button: call `currentDrawFeature.disable()`, hide drawbar, show info page
- [ ] 4.5 Wire Finish button: call `currentDrawFeature.completeShape()`
- [ ] 4.6 Hide drawbar on `draw:created` (drawing completed)

## 5. JS — Edit mode migration

- [ ] 5.1 Update `startEditMode()`: show drawbar with "Finish editing" label, hide Cancel button
- [ ] 5.2 Update `endEditMode()`: hide drawbar

## 6. Cleanup

- [ ] 6.1 Remove dead `startDrawMode()` function
- [ ] 6.2 Remove old `#draw_button` click handler
- [ ] 6.3 Remove `endDrawMode()` if no longer used

## 7. Testing

- [ ] 7.1 Manual test: polygon drawing — verify Cancel and Finish buttons appear, Finish disabled until 3 vertices
- [ ] 7.2 Manual test: line drawing — verify Cancel and Finish buttons appear, Finish disabled until 2 vertices
- [ ] 7.3 Manual test: edit mode — verify Finish editing button appears at bottom
- [ ] 7.4 Manual test: Cancel during drawing — verify shape is discarded and UI resets
