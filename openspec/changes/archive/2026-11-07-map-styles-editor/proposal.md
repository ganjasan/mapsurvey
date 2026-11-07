## Why

The library (#542) holds workspace styles, but the only way to make one is to duplicate a preset: a copy looks exactly like its source. The vision's core value (FE-3, FE-4) is a creator changing a handful of controls and seeing, before publishing, what respondents and the printed form will get. ADR 0001 settled how: the editor page alone renders the generated style in the browser with MapLibre; Save publishes a new immutable version in the background; the print preview is a Static Images frame of the last saved version.

## What Changes

- **Editor page** `/org/<slug>/map-styles/<uuid>/edit/` for a workspace style (owner/admin/editor): name, the guided controls, a live preview, a *Print* tab, *Save*.
- **Guided controls**, the generator's keys and nothing else: five removals (POI, paths, shields & arrows, relief, regional boundaries), buildings on/off, four colour roles (land, parks, water, boundaries) as bounded swatch palettes, road look (fill / casing presets: light, medium, strong), labels (major / minor palettes, bold street names), place-name zoom limit, greyscale. A hex field under each palette for a colour the swatches lack.
- **Live preview**: MapLibre GL on this page only, fed by a preview endpoint that turns the current settings into a MapLibre-readable style (base `streets-v12` cached a day, `mapbox://` sources rewritten with the public token). A survey picker frames the map at one of the workspace's surveys. Unsaved changes are marked.
- **Print tab**: the Static Images frame of the **last saved** version at the picked survey's frame, with a "photocopy" (greyscale) toggle; while there are unsaved changes it says so.
- **Contrast warnings**: parks, water, roads and labels against the land colour, judged in greyscale, shown next to the control.
- **Save** = `MapStyleVersion` number + 1, `pending`, published by the existing task; the card and the editor show the state; the respondent surfaces follow the pinning rule. **BREAKING for nothing**: a published survey keeps its pinned version.
- **Pins on live settings saves**: a published survey whose base maps are changed in place (a safe edit, no republish) is re-pinned at that save, so a later Save in the editor cannot change it.
- Library card polish: *Edit* on workspace styles, *Duplicate* + *Edit* fit on one line, *Rename* moves into the editor.
- Help page section, translations, PostHog event `map_style_saved`.

## Capabilities

### New Capabilities
- `map-style-editor`: the editor page, the preview endpoint and its style rewriting, the control set and contrast warnings, Save as a new version, print preview, re-pinning on live settings saves.

### Modified Capabilities
- `map-style-library`: the card's actions (Edit replaces Rename; Duplicate stays) — "Duplicate, rename and delete" requirement is modified to route rename through the editor.

## Impact

- New: `survey/templates/org/map_style_editor.html`, `survey/assets/js/map_style_editor.js`, `survey/assets/css/map_style_editor.css`, `survey/map_styles/preview.py` (settings → MapLibre style), `survey/tests/test_map_style_editor.py`.
- Changed: `survey/map_style_views.py` (edit, preview, save), `survey/urls.py`, `org/_map_style_cards.html`, `survey/services/surveys.py` + `services/sections.py` (re-pin on live saves), `billing` none (gate reuses `map_styles`), help page, locales.
- External: MapLibre GL 5.6 from unpkg on the editor page only; Mapbox Vector Tiles API requests from the editor (billed per tile; a creator session is a few hundred tiles); Static Images for the print tab with the public token.
- Not in this change: reference layers on the preview, custom fonts/sprites, per-layer editing, import/export (#544), API/MCP (v1.1).
