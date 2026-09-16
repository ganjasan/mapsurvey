## Context

Four creator-facing map pickers. `survey_create.html` (2026-07-04) is centre-based:
`map.getCenter()` on `moveend` into hidden fields, a fixed `.map-center-pin`, a
`touched` flag that tells creator gestures from programmatic moves. The other three —
`partials/section_map_picker.html` (Bootstrap modal, HTMX-swapped into
`#mapPickerModalBody`), `survey_settings.html` (standalone page) and
`partials/survey_settings_panel.html` (HTMX-swapped) — are click-to-place-marker with an
explicit Save button, each with its own copy of the script. The settings panel's other
fields already autosave (`[data-autosave-status]`); question edit forms autosave through
`editor_autosave.js` with `.autosave-indicator` (saved / saving / error-with-retry).

Endpoints: `editor_section_map_picker` POST (`clear_position`, `lat`, `lng`, `zoom`,
`use_geolocation`, `override_basemap`; 204, or 403 on a published/closed survey) and
`editor_survey_map_position` POST (`lat`, `lng`, `zoom`, `use_geolocation`; 204). Both
`int()` the zoom.

## Goals / Non-Goals

**Goals**
- One interaction model on every editor picker: frame the map, the centre is the answer.
- Nothing to remember to press. The creator sees "Saved" and can close the modal.
- The section "Inherit" state is always visible and always truthful.
- One script, three thin templates.

**Non-Goals**
- Touching the create page (already right; different persistence — the form).
- Changing endpoint contracts, adding server validation, a migration.
- Undo. Autosave has no Cancel; the previous position can be re-framed.
- Fixing the affected creator's rows.

## Decisions

**D1. The centre is the value; the click handler goes.**
`map.getCenter()` and `map.getZoom()` on `moveend` and `zoomend` are the position. A
`.map-center-pin` (the create page's) sits over the map container, `pointer-events: none`,
its tip on the centre. Rationale: the field is a viewport, and the click model produced a
save that looked right and wasn't. Alternative — keep click and add drag — rejected: two
models on one map is the confusion, not the cure.

**D2. Autosave, debounced, serialised, loud on failure.**
`moveend`/`zoomend` schedule a save 800 ms after the last one (the `editor_autosave.js`
constant). In-flight + queued flags serialise overlapping saves. The indicator is the
`.autosave-indicator` markup and CSS; on error it reads "Not saved — tap to retry" and a
click retries, exactly as question forms behave. No `alert()`. The `.autosave-indicator`
CSS moves out of the `{% if EDITOR_AUTOSAVE %}` block in `editor_base.html` — it is CSS,
and this change ships without a flag.

**D3. Inherit (section modal).**
- Tick → `map.flyTo(default)`, pin gets `.is-inherit` (dimmed), label "Inheriting the
  survey position", `clear_position=1` saved immediately (a checkbox is a deliberate act;
  no debounce).
- While ticked, `sync()` updates nothing but the label and schedules no save, so the fly
  itself cannot write the default back as a custom position.
- Creator gestures untick: `dragstart`, `wheel`, `dblclick`, a second touch, a click on
  the zoom control, a search result, "My location". The create page's `markTouched`
  list, verbatim. After the untick the following `moveend` saves the centre.
- Untick by hand → the centre (which is the default until they move) is saved as the
  section's own position, and the label says so. This is the case that trapped the
  reporter, and it is now honest: the pin is lit, the label shows coordinates, the next
  drag saves. Alternative — refuse to save a centre equal to the default — rejected: a
  section legitimately may start exactly where the survey does.

**D4. One module.** `MapPositionPicker.attach(map, options)` in
`survey/assets/js/map_position_picker.js`, loaded by `editor_base.html` next to
`map_place_search.js` (same reason: two of the three pickers arrive by HTMX swap and a
script inside a swapped fragment is not reliably run). Options: `url`, `csrfToken`,
`coordsEl`, `indicatorEl`, `inherit: {checkbox, lat, lng, zoom}` (section only),
`extraFields()` → object merged into every POST, `watch: [elements]` whose `change` saves
now, `locate: true` adds the "My location" control, `labels` for the four strings the
module writes. The template passes server-rendered numbers under `{% localize off %}`
as before (`EditorJsNumberLocaleTest` keeps guarding that). Returns `{save, sync}`.
`MapPlaceSearch.attach` is called by the template after the module, with
`onSelect: picker.touched` — a search is a gesture.

**D5. What refreshes.** After a successful save the module dispatches `sectionSaved` on
`document.body`; `survey_detail.html` already refreshes the Live preview on it, so the
creator sees the respondent map re-centre. The server's `HX-Trigger: mapPositionSaved`
header and the page's listener that closes the modal on it are left in place: a plain
`fetch` never sees the header, so neither runs, and removing them is a cleanup for a
change that touches the view.

**D6. Zoom is rounded** before posting. Leaflet's default `zoomSnap` yields integers at
`moveend`, but the endpoints `int()` the value and a fractional zoom from a future
`zoomSnap: 0` would 500.

## Risks / Trade-offs

- A creator who opens the modal only to look and drags will save a position. Accepted:
  the modal exists to set a position; the indicator says what happened; ticking Inherit
  undoes it.
- Preview reload per pause of movement. Same cost the settings panel already pays per
  keystroke; debounce bounds it.
- The `.map-center-pin` must sit inside a positioned ancestor. `.picker-map` already has
  `position: relative; z-index: 0`; the module appends the pin to the map container.

## Migration Plan

Deploy. No data change. Existing section positions render as before (the map opens
centred on them; the pin is on them). The reporter re-sets three sections by dragging.

## Open Questions

None.
