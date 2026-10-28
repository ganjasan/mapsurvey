## 1. Fix

- [x] 1.1 `section_map_picker.html`: pass `'{{ MAPBOX_ACCESS_TOKEN }}'` to `MapPlaceSearch.attach`
- [x] 1.2 Move the inherit/click/zoom bindings out of `onSelect`; attach the search control last, after Save, My-location and `invalidateSize`
- [x] 1.3 Tests (GIVEN/WHEN/THEN) in `EditorMapPickerSearchTest`: no bare `mapboxAccessToken` in the rendered picker; click and Save bindings precede the search attach; `onSelect` holds no handler bindings

## 2. Verify and ship

- [x] 2.1 Run `EditorMapPickerSearchTest` and the localisation guard test; then the survey suite
- [x] 2.2 Drive the picker in a browser against the dev server: untick Inherit, click, Save, confirm the row in the DB
- [ ] 2.3 PR, merge; confirm the PostHog issue stops recurring
- [ ] 2.4 Send the prepared reply to the BC3 creator
