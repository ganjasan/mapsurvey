# Tasks

## 1. Fix
- [x] 1.1 `section_map_picker.html`: `accessToken: '{{ MAPBOX_ACCESS_TOKEN }}'` instead of the undefined `mapboxAccessToken` global
- [x] 1.2 `section_map_picker.html`: move `clearCb` change listener, initial `updatePickerState()`, map `click` and `zoomend` handlers out of `onSelect` into the picker scope
- [x] 1.3 Guard test: no template under `survey/templates/editor/` references `mapboxAccessToken` or `mapboxUrl` as a bare identifier

## 2. Verification
- [x] 2.1 `./run_tests.sh survey -v2` green
- [ ] 2.2 Browser: open a section picker, untick Inherit, click the map, Save, reopen → the clicked coordinates are shown
- [ ] 2.3 Browser: search a place in the picker, Save, reopen → the searched coordinates are shown (the #174 path still works)
