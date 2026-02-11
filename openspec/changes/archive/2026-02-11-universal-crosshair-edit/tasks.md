## 1. Universal crosshair for point placement

- [x] 1.1 In `base_survey_template.html`, remove the `isTouchDevice` conditional in `.drawpoint` click handler — always call `showCrosshair(color, icon)` and set `currentQ`
- [x] 1.2 In `base_survey_template.html`, remove the `L.Draw.Marker` instantiation branch from the `#draw_button` `start_draw` mode handler (the `drawpoint` sub-branch)
- [x] 1.3 Verify that the `isTouchDevice` variable is no longer referenced anywhere; remove it if unused

## 2. Crosshair edit mode state management

- [x] 2.1 Add `crosshairEditLayer` variable (initialized to `null`) alongside existing state variables in `base_survey_template.html`
- [x] 2.2 Modify `showCrosshair()` to also accept an optional layer parameter and store it in `crosshairEditLayer`
- [x] 2.3 Modify `.crosshair-apply` handler: if `crosshairEditLayer` is set, move the marker to `map.getCenter()` and restore visibility instead of firing `draw:created`
- [x] 2.4 Modify `.crosshair-cancel` handler: if `crosshairEditLayer` is set, restore the marker's visibility and original position, then clear `crosshairEditLayer`
- [x] 2.5 Ensure `crosshairEditLayer` is cleared to `null` after both Apply and Cancel

## 3. Edit button crosshair integration

- [x] 3.1 In `survey_section.html` `onPopupOpen`, modify `.layer-edit` click handler: check if the layer is an `L.Marker` instance
- [x] 3.2 For `L.Marker` layers: close popup, store original LatLng, hide marker (setOpacity or remove from map), pan map to marker position, call `showCrosshair(color, icon, layer)`
- [x] 3.3 For non-`L.Marker` layers: keep existing `startEditMode(tempLayer)` call
- [x] 3.4 Extract the marker's color and icon from the button element using `props.question_id` to find the matching `.drawbutton`

## 4. Marker visibility during crosshair edit

- [x] 4.1 When entering crosshair edit, hide the original marker (test `setOpacity(0)` with `L.Icon.FontAwesome`; fall back to `editableLayers.removeLayer` + re-add if needed)
- [x] 4.2 On Apply, restore marker visibility and update its LatLng
- [x] 4.3 On Cancel, restore marker visibility at original position

## 5. Testing and verification

- [ ] 5.1 Manual test: desktop point placement uses crosshair (no `L.Draw.Marker` ghost cursor)
- [ ] 5.2 Manual test: mobile point placement still works via crosshair
- [ ] 5.3 Manual test: click Edit on existing point marker → crosshair appears, pan map, Apply → marker moves to new position
- [ ] 5.4 Manual test: click Edit on existing point marker → crosshair appears, Cancel → marker stays at original position
- [ ] 5.5 Manual test: click Edit on line/polygon → drag handles appear (existing behavior unchanged)
- [ ] 5.6 Manual test: sub-question properties are preserved after crosshair edit
- [ ] 5.7 Verify form submission produces correct GeoJSON for markers placed/edited via crosshair
