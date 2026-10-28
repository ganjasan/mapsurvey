## Why

Five creators — including the VIA eG (Cologne) and Uni Bremen accounts — hit three
separate defects on the editor's map surfaces between 2026-09-04 and 2026-09-18. PostHog
session replay surfaced them as the highest-frustration sessions in the project: repeated
page reloads, dead clicks on **Import GeoJSON**, and rage clicks on an error toast. All
three are live on `origin/master` today.

They are not three unrelated slips. Four editor templates embed a Leaflet map in inline
JavaScript, and that inline JS keeps breaking under conditions an English-speaking
developer never reproduces:

1. **A localized decimal comma kills the layer object editor.** `layer_editor.html:234`
   interpolates raw floats into `setView([...])`. Under any of the ten comma-decimal
   creator languages Django renders `50.9375` as `50,9375`, so `setView([50,9375, 6,9603], 12)`
   receives a four-element array, Leaflet's map pane never gets a position, and every
   subsequent mouse move throws `TypeError: … reading 'x'`. Page init dies with it, so the
   import buttons do nothing. 251 events, 100% on `de`/`nl`/`pl`, zero on `en`. The first
   event landed 11 minutes after `#155` merged (2026-09-04 18:36 UTC).

   This exact defect was fixed on 2026-08-30 in `e2ba265` for the three sibling templates,
   but the guard test was pinned to two hardcoded URLs, so the fourth map template — added
   six days later — reintroduced it and shipped green.

2. **`#192` reintroduced a fragility in the same three templates.** `MapPositionPicker`'s
   `extraFields()` dereferences `document.getElementById(...).checked` with no null guard.
   When debounced autosave fires after HTMX has swapped the settings panel away, the
   element is gone, the callback throws, and the creator's map position is silently lost.

3. **A 3D GeoJSON upload returns 500 instead of importing.** `layers.py:387` and
   `layer_object_views.py:113` hand GeoJSON straight to `GEOSGeometry`; `LayerObject.geometry`
   is a 2D column, so a file carrying Z coordinates — the QGIS and ArcGIS default — fails
   with `DataError: Geometry has Z dimension but column does not`. The browser receives an
   HTML error page where it expects JSON and shows the creator
   `Unexpected token '<', "<!DOCTYPE "… is not valid JSON`. One creator retried six times
   across two surveys and two days.

Now, because the layer object editor is how our first institutional customer builds their
reference data, and because the pattern will recur on the next map template unless the
guard stops being URL-specific.

## What Changes

- Wrap the coordinate block in `editor/layer_editor.html` in `{% localize off %}`, matching
  the three templates already guarded.
- Replace the two URL-pinned localization tests with a guard that walks **every** template
  rendering coordinates into a `<script>` block, so a new map page cannot ship unguarded.
- Null-guard `extraFields()` in all three `MapPositionPicker.attach` call sites, and cancel
  the pending autosave timer when the panel is detached, so a swap cannot drop a save.
- Coerce imported geometry to 2D at every GeoJSON ingestion point (bulk import, single-object
  create, ZIP import) rather than letting the database reject it.
- Return a structured JSON error from the layer endpoints on invalid geometry, so the
  creator sees a sentence about their file instead of a JSON parse error.

No behaviour changes for creators working in English, and no change to stored geometry for
layers already imported.

## Capabilities

### New Capabilities

_None._ All three defects are failures of behaviour already specified elsewhere.

### Modified Capabilities

- `ui-internationalization`: the requirement that localized numbers never reach inline
  JavaScript moves from "these two pages are checked" to "no template emits a
  locale-formatted number into a script block", enforced repository-wide.
- `reference-overlay-layers`: GeoJSON import SHALL accept 3D coordinates by discarding the
  Z ordinate, and SHALL report an invalid file as a structured error rather than a 500.
- `survey-editor`: map position autosave SHALL survive the panel being swapped out mid-flight
  — either by completing or by being cancelled, never by throwing.

## Impact

**Templates**
- `survey/templates/editor/layer_editor.html` (line 234)
- `survey/templates/editor/partials/survey_settings_panel.html` (line 310)
- `survey/templates/editor/partials/section_map_picker.html` (line 111)
- `survey/templates/editor/survey_settings.html` (line 182)

**Python**
- `survey/layers.py::objects_from_features` (line 387)
- `survey/layer_object_views.py` (lines 113, 495)
- `survey/editor_views.py::editor_survey_layer_create` (error response shape)

**JavaScript**
- the `MapPositionPicker` helper introduced by `#192` (timer teardown)

**Tests**
- `survey/tests.py` — the localization guard class (~line 36586) is generalized; new cases
  for 3D import and for autosave after panel teardown.

**Dependencies / risk**
- Local `master` is one commit behind `origin/master`; `#192` (`59ea01d`) must be present
  before touching the picker call sites. Branch from `origin/master`, not local `master`.
- No migration. `LayerObject.geometry` stays 2D — this change stops sending it 3D input.
