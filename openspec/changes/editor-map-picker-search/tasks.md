## 1. Script availability

- [x] 1.1 Include `js/components/map_place_search.js` in `editor/editor_base.html` and `editor/survey_settings.html`

## 2. Survey pickers (settings page + in-editor panel)

- [x] 2.1 Add a search container above `#survey-map-picker` in both templates and attach `MapPlaceSearch` with the Mapbox token and the create-page placeholder label
- [x] 2.2 `onSelect`: set lat/lng/zoom, place or move the marker, update `#survey-map-coords` (same code path as click)
- [x] 2.3 Sizing: settings-page map 460px and its section `max-width: none` at ≥1024px; panel map 380px at ≥1024px; existing heights below

## 3. Section modal

- [x] 3.1 Add the search container above `#map-picker`, attach after the map initialises inside the modal timeout
- [x] 3.2 `onSelect`: uncheck `#clear-position`, run `updatePickerState()`, then set position/marker/zoom/label as a click would
- [x] 3.3 Modal `modal-lg`, map 480px at ≥1024px

## 4. Verification

- [x] 4.1 Template tests: search input rendered on settings page, panel, and section modal with a token; absent without a token; Save endpoints unchanged
- [x] 4.2 Browser check at 1280px and 390px: search→save on all three pickers; inherit checkbox behaviour in the modal; dropdown not clipped by the modal or map
- [x] 4.3 `./run_tests.sh survey -v2` green
