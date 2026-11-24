## Why

Three different needs share one mechanism, and creators get stuck between them (#779). Since
`layers-by-question` a reference layer is on a section's map only when an "Objects on the map"
question binds it, so a creator who uploads a boundary sees it nowhere (a support email on
2026-11-23; 12 of 87 uploaded layers are on no map), and 503 of 605 Objects questions exist only to
show a layer. Meanwhile the most common layer is a hand-made study-area boundary (39 of 87 layers
have three objects or fewer; 18 live surveys in 11 workspaces, #303), which a reference layer
cannot do: respondents pan away and mark outside it.

## What Changes

- **A reference layer is shown by its placement on the map, not by a question.** A map section's
  *Map* card in Build lists the layers on that map and has *+ Layer* (upload a file / from Data /
  draw). Each layer has a scope: **every section, now and later** (default; sections added later
  get it) or **only the sections picked**.
- **An "Objects on the map" question only asks.** Its body is its sub-questions; picking a layer
  that is not on the section places it there. The List / Legend switch goes; a question without
  sub-questions points the creator back to the Map card. **BREAKING** (editor behaviour): the
  question no longer decides visibility.
- **Migration:** every legend-only Objects question (no sub-questions) becomes a placement of its
  layer on its section and is deleted; respondents of existing surveys see the same layers in the
  same legend order.
- **The study area is its own survey-level object, never a layer** (#303): set by a place name
  (an OpenStreetMap boundary), then edited by moving vertices; a file, a layer of the survey or a
  drawing are secondary sources. The map opens on it, a fog covers the rest, and an optional rule
  refuses map answers outside it — in the browser and again on the server. A street found by name
  becomes a corridor of a picked width; a place OpenStreetMap knows only as a point starts as a
  rectangle. It frames the printed form's map, and its outline shows on the Responses map and in
  Reports map blocks.
- **Layers live in Data.** An upload from the survey goes through the Data import (GeoPackage,
  zipped shapefile, KML, GeoJSON, CSV; reprojected to WGS 84 instead of refused) and becomes a
  public layer dataset the survey references. The Survey-settings card becomes "Layers used
  here", pointing at Data.
- **Publish check** lists the study area and every layer with where it shows, and flags a layer
  that is on no map.
- Placements and the study area are writable through the service layer, REST v1 and MCP on ship
  day.

## Capabilities

### New Capabilities
- `map-layer-placement`: putting reference layers on section maps — the Map card, placement
  scope, the legend built from placements, the publish check, the migration from legend-only
  questions, API/MCP parity.
- `survey-study-area`: the survey boundary — sources (place name, file, layer, drawing), vertex
  editing, fog outside, the optional refusal of map answers outside (client and server), API/MCP
  parity.

### Modified Capabilities
- `reference-overlay-layers`: uploads go through the Data import (formats, reprojection) and
  produce a public layer dataset; visibility per section comes from placements; the editor
  preview follows placements; the settings card lists "Layers used here".
- `layer-objects-question`: the question asks about a layer's objects; it no longer shows a layer
  by itself; picking a layer places it; List / Legend mode removed.
- `data-links`: a survey's own upload is a dataset like any other; placing a workspace dataset on
  a survey map is the link; the guards apply to placements.
- `survey-editor`: the requirement "Layers are put on a map by adding a question" (from
  `layers-by-question`) is replaced by the Map card.
- `survey-serialization`: the ZIP carries placements and the study area; archives with legend-only
  questions or `hidden_layers` import as placements.
- `printable-form`: a printed map section is framed on the study area and shows its outline.
- `ai-survey-generation`: the Wizard always sets the study area of the place the brief names, with handles on the create page (edit the outline, corridor width, refusal, remove); the place prefill ranks candidates by place type.

## Impact

- **Models:** new `LayerPlacement` (layer, scope, section codes, order) and `StudyArea` (canonical
  survey, polygon, source, fog, refuse-outside, message); `Question.panel_mode` retired;
  `SurveySection.hidden_layers` dropped (pending since `layers-by-question`).
- **Code:** `survey/layers.py` (`section_layer_ids`, `build_map_layers_metadata`),
  `partials/reference_layers.html`, the section panel and settings card templates, the Objects
  question form, `survey/services/`, `data/imports.py` / `data/links.py`, the section POST
  (geometry check), `survey/serialization.py`, the printable form, `api/v1/`, `mcp/tools/`.
- **New outbound dependency:** a boundary lookup by place name (Nominatim `polygon_geojson`),
  creator-initiated only, never on respondent pages.
- **Order of work:** `layers-by-question` must be archived first — this change modifies the
  requirements it adds.
- **Help centre:** the reference-layers guide is rewritten; a study-area page is added.
