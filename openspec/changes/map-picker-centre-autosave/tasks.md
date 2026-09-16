## 1. Module

- [x] 1.1 `survey/assets/js/map_position_picker.js`: `MapPositionPicker.attach(map, options)` — centre pin, `sync()` on `moveend`/`zoomend`, debounced serialised save, indicator states with click-to-retry, `inherit` handling (tick → fly + save clear; gestures untick), `watch` elements save on change, optional locate control, `sectionSaved` dispatch, `{save, sync, touched}` return
- [x] 1.2 `editor_base.html`: include the module after `map_place_search.js`; move `.autosave-indicator` CSS out of the `EDITOR_AUTOSAVE` gate; add `.map-center-pin` / `.is-inherit` CSS beside the `.picker-map` rules

## 2. Templates

- [x] 2.1 `section_map_picker.html`: drop marker/click/Save/Cancel/alert script; hint text for dragging; pin-carrying map; indicator in the footer with a Close button; attach the module with `inherit`, `extraFields` (geolocation, basemap), `watch` on both, `locate`; then `MapPlaceSearch.attach` with `onSelect: picker.touched`
- [x] 2.2 `survey_settings.html`: same, without `inherit`; `extraFields` → `use_geolocation`, `watch` on that checkbox; remove the Save button and the "Saved!" span
- [x] 2.3 `survey_settings_panel.html`: same as 2.2
- [x] 2.4 Strings: new hint / label / indicator strings in the ten UI-language catalogs, `.mo` recompiled

## 3. Tests

- [x] 3.1 `EditorMapPickerSearchTest`: replace the click/Save-binding assertions with: module attached on all three surfaces, no `map.on('click'`, no `#save-map-position` / `#save-survey-map-position`, indicator present, section modal passes `inherit`, search `onSelect` is `picker.touched`; module script included by `editor_base.html` (manifest-hash regex like the search one)
- [x] 3.2 Section endpoint round trip: `clear_position=1` nulls position and zoom; `clear_position=0` with coordinates stores them (the survey-level test exists)
- [x] 3.3 `EditorJsNumberLocaleTest` still green (initial values remain under `localize off`)

## 4. Verification

- [x] 4.1 `./run_tests.sh survey` green
- [x] 4.2 Browser, 1280px: section modal — untick, drag, watch label and "Saved", close, reopen → map opens on the dragged centre; tick Inherit → flies to default, "Saved", reopen → checkbox ticked; search "Tallinn" while ticked → unticks and saves; settings page and panel — drag → "Saved", reload → kept
- [x] 4.3 Browser, 390px: the pin sits on the centre in the full-screen modal; drag saves
