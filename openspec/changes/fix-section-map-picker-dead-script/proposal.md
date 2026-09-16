# Fix: the section map picker script dies before it wires anything up

## Why
A creator (Megan Critchley, 2026-09-16) reported that in the section map picker she can
untick "Inherit position", move the map and click Save — but reopening the picker shows
the position reset. Two independent defects in
`editor/partials/section_map_picker.html` produce exactly that:

1. **`mapboxAccessToken` is undefined.** #180 deleted the `var mapboxUrl` /
   `var mapboxAccessToken` pair from this template when `basemap_layers.html` stopped
   reading them from the enclosing scope, but line 125 still passes
   `accessToken: mapboxAccessToken` to `MapPlaceSearch.attach`. Evaluating that object
   literal throws `ReferenceError`, and everything registered *after* the call never
   runs: the Save handler, the "My location" control and `invalidateSize()`. Save has
   been a no-op for every creator since #180 merged (2026-09-14). This is the second
   regression from that same global rename.

2. **The picker's handlers are nested inside the search callback.** A brace error in
   #174 swallowed `clearCb.addEventListener`, the initial `updatePickerState()`, the
   map `click` handler and the `zoomend` handler into
   `MapPlaceSearch.attach`'s `onSelect` body. Even with defect 1 fixed, clicking the map
   would set no marker and update no coordinate, the Inherit checkbox would not gate the
   map, and each search result would re-register all four handlers.

Together: the creator unticks Inherit (no effect), clicks the map (no effect — `lat`/`lng`
keep the inherited values), clicks Save (no handler at all), and the section keeps
whatever it had. Exactly the report.

## What changes
- `section_map_picker.html` passes `'{{ MAPBOX_ACCESS_TOKEN }}'` directly, the way the
  other three pickers already do — no template-scope global to forget.
- The four swallowed statements move out of `onSelect` to the picker's own scope.
- A template guard test asserts no editor template references a `mapboxUrl` /
  `mapboxAccessToken` scope global, so the #180 class of breakage cannot come back.
- Spec: the picker requirement gains scenarios for click-to-set and for the Save round
  trip, which no scenario covered end to end.

## Out of scope
The picker's JavaScript lives inline in a template, which is why neither defect was
visible to any test. Extracting it to `survey/assets/js/` is the real fix and belongs to
its own change.
