## Why

Once a survey exists, the only way to move its start position is to drag a 300px-tall map
inside an 800px settings column (or the 400px section modal) across continents and click.
There is no place search on any of the three editor pickers, although the shared
`MapPlaceSearch` control already exists and is used on the create page and by respondents.
A creator who briefed a survey about Tallinn and got Berlin — the case that triggered the
sibling change `create-map-location-from-brief` — has to fix it by hand, and today that is
slow on desktop and near-impossible on a phone.

## What Changes

- The shared place-search control is attached to all three editor map pickers: the
  standalone survey settings page, the survey settings panel inside the editor, and the
  section map-position modal. Choosing a result moves the map AND sets the picked position
  to the result point, so "search Tallinn, save" is a complete edit; a click still refines.
- The settings-page map gets room: taller on desktop and allowed to break out of the narrow
  settings column; the section modal opens wide with a taller map; the in-editor panel map
  gets taller. Mobile heights are unchanged.
- The search script is loaded once by the editor base template so the HTMX-swapped panel
  and modal find it; the standalone settings page loads it itself.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `survey-editor`: the section map position picker gains place search and a wider layout;
  a survey-level default map position picker with the same search is specified (it exists
  today but had no requirement).

## Impact

- `survey/templates/editor/editor_base.html`, `survey/templates/editor/survey_settings.html`,
  `survey/templates/editor/partials/survey_settings_panel.html`,
  `survey/templates/editor/partials/section_map_picker.html` — script include, search
  container, size CSS, `onSelect` wiring to the picker state.
- `survey/assets/css/main.css` or editor CSS — picker sizing rules.
- No Python, model or migration changes; the save endpoints are untouched.
- Mapbox Search Box requests from three more surfaces, creator-only and typing-paused, so
  the cost is bounded the same way as on the create page.
