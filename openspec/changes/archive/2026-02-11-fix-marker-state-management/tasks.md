## 1. Disable draw handler on feature creation

- [x] 1.1 In `survey_section.html` `draw:created` handler, add `if (currentDrawFeature) { currentDrawFeature.disable(); currentDrawFeature = null; }` as the first lines, before `editableLayers.addLayer(layer)` and `layer.openPopup()`
- [x] 1.2 Verify that `endDrawMode()` (called from Apply button and no-subquestion branch) still works as a no-op when `currentDrawFeature` is already null

## 2. Single-edit mode with dedicated tracking variable

- [x] 2.1 In `base_survey_template.html`, add `var currentEditLayer = null;` alongside the existing state variables
- [x] 2.2 In `startEditMode(layer)`, add a guard: if `currentEditLayer` is not null, call `currentEditLayer.editing.disable()` before proceeding. Then set `currentEditLayer = layer`
- [x] 2.3 In `endEditMode(layer)`, set `currentEditLayer = null` after disabling editing
- [x] 2.4 Stop setting `currentDrawFeature = layer` in `startEditMode` — use `currentEditLayer` instead. Update `draw_button` click handler's `end_edit` branch to call `endEditMode(currentEditLayer)` instead of `endEditMode(currentDrawFeature)`

## 3. Unique popup form IDs

- [x] 3.1 In `survey_section.html` `draw:created` handler, compute `var formId = 'subquestion_form_' + L.Util.stamp(layer);` and use it in the popup HTML `id` attribute
- [x] 3.2 In the existing-answers restoration loop, apply the same pattern: compute unique form ID from `L.Util.stamp(layer)` for each restored layer's popup HTML
- [x] 3.3 Store the form ID on the layer for later retrieval: `layer._formId = formId;`

## 4. Scope form serialization to popup container

- [x] 4.1 In `onPopupOpen`, replace global `$('*[name=' + key + ']')` queries with queries scoped to the popup container: `var popup = this.getPopup().getElement(); var $form = $(popup).find('form');` then query within `$form`
- [x] 4.2 In the Apply button handler (inside `onPopupOpen`), replace `$('#subquestion_form').serializeArray()` with `$('#' + tempLayer._formId).serializeArray()`
- [x] 4.3 In `onPopupClose`, replace `$('#subquestion_form').serializeArray()` with `$('#' + this._formId).serializeArray()`

## 5. Manual testing

- [ ] 5.1 Test: place a point marker on desktop, confirm draw tool deactivates and clicking the map does NOT create another marker
- [ ] 5.2 Test: place a point via mobile crosshair, confirm popup opens and no extra markers appear
- [ ] 5.3 Test: place two markers with sub-questions, fill in different data for each, submit — confirm data is saved correctly per marker
- [ ] 5.4 Test: edit one marker's position, then edit a second marker's position — confirm the first marker exits edit mode cleanly (no duplication)
- [ ] 5.5 Test: draw a line and polygon, confirm draw tool deactivates after each
- [ ] 5.6 Test: navigate back to a section with existing geo answers, confirm restored markers have working popups with correct data
