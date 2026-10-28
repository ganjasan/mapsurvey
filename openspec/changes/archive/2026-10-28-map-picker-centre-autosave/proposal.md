## Why

A creator (BC3, 2026-09-16) set three sections of one survey to three districts of
Vitoria-Gasteiz and got the survey default on all three. The picker only takes a position
from a **click**; she **dragged** the map, as the create page had taught her, and the
label — rewritten by `zoomend` with the never-changed coordinates — showed the survey
default as if it were her choice. Save then wrote that default into two sections as their
"own" position and left the third empty. In the database: sections 1138 and 1140 hold
42.86252, −2.68869, zoom 15 — the survey header's values to five decimals; districts on
opposite sides of the city.

Three of the four editor map pickers work this way (section modal, settings page, settings
panel). They date from the first WYSIWYG editor (2026-02-13) and copied the GeoDjango admin
idiom for a `PointField`: click to place a marker. The create page was reworked on
2026-07-04 with the model the field actually has — a **viewport**: wherever the creator
frames the map is where respondents start, the pin is glued to the centre, and there is
nothing to click. Nobody went back for the other three. The spec even records the click as
a requirement.

The section modal has a second trap: unticking "Inherit position" on a section with no
position of its own changes nothing on screen (no marker, label still says "Inheriting"),
so a creator cannot tell the checkbox did anything.

## What Changes

- **Centre is the value** on all three pickers. A fixed pin marks the centre of the map;
  dragging, zooming, searching and "My location" all move the map and thereby set the
  position. The map click handler is removed.
- **Autosave.** Every settled move (`moveend`/`zoomend`, debounced) posts to the existing
  endpoint; a saved/saving/error indicator replaces the Save button (and the modal's
  Cancel). The section modal's geolocation checkbox and basemap override save on change
  through the same call.
- **Inherit, section modal.** Ticking it flies the map to the survey default at once, dims
  the pin, and saves the cleared position. Any creator gesture on the map while it is
  ticked — drag, wheel, pinch, zoom buttons, a search result, "My location" — unticks it,
  because moving the map is how a section gets its own position. Programmatic moves
  (the fly to default, a search flight) never untick it.
- **One module**, `js/map_position_picker.js`, replaces the three inline scripts; the
  templates keep only the HTML and the server-rendered initial values.
- Spec: both picker requirements rewritten from "click to set" to "centre of the map";
  scenarios for drag-to-set, inherit tick/untick and autosave.

## Out of scope

- The create page picker: already centre-based, saves with its form. Left as is.
- The save endpoints and their contract (`lat`, `lng`, `zoom`, `clear_position`,
  `use_geolocation`, `override_basemap`). Unchanged.
- The affected creator's rows (sections 933, 1138, 1140 of survey 526). Owner decision
  2026-09-16: not touched; she sets them again once this ships.
- Any kill switch. Ships unconditionally; the rollback is a revert.

## Capabilities

### Modified Capabilities

- `survey-editor`: "Section map position picker" and "Survey default map position picker"
  — interaction model and persistence.

## Impact

- `survey/assets/js/map_position_picker.js` (new), `survey/templates/editor/editor_base.html`
  (script include, pin and indicator CSS out of the `EDITOR_AUTOSAVE` gate),
  `survey/templates/editor/partials/section_map_picker.html`,
  `survey/templates/editor/survey_settings.html`,
  `survey/templates/editor/partials/survey_settings_panel.html`.
- `survey/tests.py`: `EditorMapPickerSearchTest` assertions on click/Save bindings replaced.
- `survey/locale/*/django.po` for the ten UI languages: new hint and indicator strings.
- No Python view, model or migration changes.
