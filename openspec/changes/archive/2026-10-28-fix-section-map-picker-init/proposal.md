## Why

Since PR #180 (merged 2026-09-14) the section map picker is dead for every creator. The PR
renamed the token global in `partials/basemap_layers.html` from `mapboxAccessToken` to
`_mapboxToken`; `editor/partials/section_map_picker.html`, which includes that partial, still
passed the old name to the place-search control. Its init callback throws
`ReferenceError: mapboxAccessToken is not defined` before the Save, click, inherit-toggle and
My-location handlers are bound, so the modal shows a map and "Save Position" does nothing.
PostHog error tracking (issue `01a0a306-aa3f-7460-aa3a-6dbd5225811e`): 15 occurrences, 4
creators, all on 2026-09-15. One of them (BC3, survey 526) opened the picker eleven times and
then wrote in that "the map position is always the same as the first one I set"; all six of her
sections have `start_map_postion = NULL`.

Underneath sits an older defect from PR #174 (2026-09-09): the inherit-checkbox listener, the
initial `updatePickerState()`, and the click and zoomend handlers ended up INSIDE the search
control's `onSelect` callback through a misplaced closing brace. Between 09-09 and 09-14 the
map ignored clicks until a place was searched, and Save wrote the survey centre with the
current zoom. The two survey-level pickers (settings page, in-editor panel) have neither
problem: they pass the token as a literal and bind their handlers before attaching search.

## What Changes

- The section picker passes `'{{ MAPBOX_ACCESS_TOKEN }}'` as a literal, like the other two
  pickers. It no longer depends on a global that another partial happens to declare.
- Click, zoom, inherit and Save handlers, the My-location control and `invalidateSize` are bound
  first; the search control is attached last. A failure inside the search control can then only
  cost the search box, never the picker.
- Tests: the rendered picker contains no bare `mapboxAccessToken`; every handler binding
  precedes `MapPlaceSearch.attach`; the search callback contains no handler bindings.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `survey-editor`: "Section map position picker" — works by click without a prior search, and
  survives a search control that fails to initialise.

## Impact

`survey/templates/editor/partials/section_map_picker.html` (script block only),
`survey/tests.py`. No migration, no endpoint change, no model change. Positions the affected
creators tried to save between 09-09 and now were never written; they set them again.
