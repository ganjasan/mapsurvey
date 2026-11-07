# map-style-editor Specification

## Purpose
How a creator changes a workspace map style (epic #545, ADR 0001): the editor page with the guided controls of `survey/map_styles/controls.py`, the preview endpoint that renders the current settings for MapLibre in the browser, Save as a new immutable published version, the re-pinning of live surveys on base-map edits, the print tab over the last published version, and contrast warnings that advise without gating.
## Requirements
### Requirement: The editor page edits a workspace style with bounded controls
`/org/<slug>/map-styles/<uuid>/edit/` SHALL open for owners, admins and editors of the workspace that owns the style, SHALL answer 404 for a preset or another workspace's style, and SHALL render exactly the controls of `survey/map_styles/controls.py::CONTROLS`: removals (POI, paths, shields, relief, regions), buildings, land / park / water / boundary colours as swatch palettes with a hex field, road look presets, label colours and bold street names, place-name zoom limit, greyscale. A posted settings document SHALL be cleaned against the same schema: unknown keys dropped, colours `#rrggbb` only, enumerations enforced.

#### Scenario: Editor opens for an editor
- **WHEN** a member with the editor role opens the editor of the workspace's style
- **THEN** the page renders the style's name and every control with the values of the latest version's settings

#### Scenario: Presets and foreign styles have no editor
- **WHEN** the editor URL names a preset or a style of another workspace
- **THEN** the response is 404

#### Scenario: Settings are cleaned
- **WHEN** a save posts `{"park": "red", "foo": 1, "roads": "strong", "place_names_maxzoom": 40}`
- **THEN** `park` is refused with a field error, `foo` is dropped, `roads` becomes the strong preset's triple and `place_names_maxzoom` is clamped to 16

### Requirement: The preview endpoint renders the current settings for MapLibre
`POST .../preview.json` SHALL take a settings document and answer a Mapbox GL style built by the generator over the cached `streets-v12` base, rewritten for MapLibre: `mapbox://` glyph, sprite and tile sources become `https://api.mapbox.com/...` URLs carrying the public token; `fog`, `projection`, `terrain`, `imports` are absent. It SHALL be gated like the editor, SHALL store nothing, and SHALL answer 503 when the base style cannot be fetched.

#### Scenario: Rewritten style
- **WHEN** the endpoint receives `{"poi": false, "park": "#dcefd2"}`
- **THEN** the answer has no layer with `source-layer` `poi_label`, `landcover.paint.fill-color` is `#dcefd2`, every source `url` starts with `https://api.mapbox.com/v4/` and contains the public token, `glyphs` and `sprite` are `https://` URLs, and no `fog` or `projection` key exists

#### Scenario: Viewer is refused
- **WHEN** a member with the viewer role posts to the preview endpoint
- **THEN** the response is 403

### Requirement: Save publishes a new version and leaves live surveys where they are
Saving SHALL create `MapStyleVersion` number `last + 1` with the cleaned settings, status `pending`, enqueue `publish_map_style_version`, record the name, and emit `map_style_saved`. Saving SHALL need the `map_styles` feature (plan or trial) and SHALL NOT consume a trial allowance. While the latest version is `pending`, a further save SHALL be refused with 409. A published survey pinned to an earlier version SHALL keep showing it.

#### Scenario: Save creates version 2
- **WHEN** an editor saves changed settings on a style with one ready version
- **THEN** version 2 exists as `pending` with those settings, the task is enqueued with its id, and the survey that pins version 1 still resolves to version 1's tiles

#### Scenario: Save while pending
- **WHEN** a save is posted while the latest version is `pending`
- **THEN** the response is 409 and no version is created

#### Scenario: Free workspace with a spent trial
- **WHEN** a save is posted in a Free workspace whose trial allowance for `map_styles` is spent
- **THEN** the response is the Pro-required page and no version is created

### Requirement: Live base-map edits re-pin the survey
When a published or closed survey's `basemaps`, `default_basemap` or a section's `override_basemap` is saved in place (a content edit), the survey's `basemap_pins` SHALL be set to the latest ready versions of the styles it now names, so a version saved later in the editor does not change it.

#### Scenario: Settings edit on a live survey
- **WHEN** a published survey with empty pins gets `basemaps=['style:<uuid>']` through the settings service, and version 2 of that style then becomes ready
- **THEN** the survey's pins name version 1 and its respondent page keeps version 1's tiles

#### Scenario: Draft is not pinned
- **WHEN** the same edit is made on a draft survey
- **THEN** its pins stay empty

### Requirement: The print tab shows the last saved version
The editor SHALL show a *Print* tab with the Static Images frame of the latest **ready** version at the picked survey's frame, with a greyscale toggle, and SHALL say when unsaved changes or a pending version mean the print view lags behind.

#### Scenario: Print frame URL
- **WHEN** the editor renders for a style whose latest ready version is `artemkonuchov/abc` and the picked survey starts at (55.68, 12.57) zoom 13
- **THEN** the print tab's image URL names that style id, the frame's centre and `fresh=true`

### Requirement: Contrast warnings are advice, not a gate
The editor SHALL compute the greyscale luminance difference between parks, water, road casing, major and minor labels and the land colour and SHALL show a warning under a control whose difference is below 0.12; warnings SHALL NOT block saving.

#### Scenario: Pale parks on white
- **WHEN** land is `#ffffff` and parks `#f4f9f0`
- **THEN** the parks control shows the photocopy warning and Save still works

