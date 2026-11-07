# map-style-import-export Specification

## Purpose
A map style as a portable file (epic #545, vision FE-6): the `mapsurvey-map-style` document, export from the library (workspace styles and rebuildable presets), import with validation through the editor's control schema and name suffixing, and the Pro rules around both.
## Requirements
### Requirement: The export is one self-contained JSON document
`GET /org/<slug>/map-styles/<uuid>/export.json` SHALL download a JSON file with `format` `mapsurvey-map-style`, `version` 1, the style's `name`, its `base`, its latest version's `settings` and `exported_at`, and SHALL carry no Mapbox style id, no uuid and no workspace reference. It SHALL be available for the workspace's styles and for presets the generator can rebuild, answer 404 for Satellite and Topo, and need the `map_styles` feature in force and the editor role or above.

#### Scenario: Export of a workspace style
- **WHEN** an editor of a Pro workspace exports a style whose latest version has `park: #cfe6b8` and Mapbox id `artemkonuchov/abc`
- **THEN** the response is an attachment named after the style whose JSON has `format`, `version: 1`, the name, `base: mapbox/streets-v12`, `settings.park == #cfe6b8`, and the text `artemkonuchov/abc` appears nowhere in it

#### Scenario: Export of presets
- **WHEN** Paper A and Satellite are exported
- **THEN** Paper A downloads with `preset: paper` and Satellite answers 404

### Requirement: Import creates a workspace style from a valid document
`POST /org/<slug>/map-styles/import/` with a file SHALL refuse a file over 64 KB, a non-object, a wrong `format`, a `version` above 1, an unsupported `base`, a missing name or settings that fail the control schema, naming the reason on the library page; otherwise it SHALL create a workspace style named like the document — with ` (2)`, ` (3)` … appended when the name is taken — whose version 1 is `pending` with the normalised settings, enqueue `publish_map_style_version`, count one `map_styles` use, and emit `map_style_imported`.

#### Scenario: Round trip
- **WHEN** a style is exported and the file is imported into another workspace
- **THEN** that workspace has a new style of the same name whose version 1 settings equal the exported settings as the editor's control schema normalises them, and is pending publication

#### Scenario: Name taken
- **WHEN** a document named "House style" is imported into a workspace that already has "House style"
- **THEN** the new style is named "House style (2)"

#### Scenario: Unknown keys are dropped, bad colours refused
- **WHEN** a document's settings carry `"layers": [...]` and `"water": "blue"`
- **THEN** the import is refused naming `water`, and a document with only the extra `layers` key imports without it

#### Scenario: Wrong format or version
- **WHEN** the file is not JSON, or `format` is not `mapsurvey-map-style`, or `version` is 2
- **THEN** nothing is created and the page says the file is not a Mapsurvey map style (or needs a newer Mapsurvey)

#### Scenario: Free workspace with a spent trial
- **WHEN** an import is posted in a Free workspace whose `map_styles` allowance is spent
- **THEN** the Pro-required page answers and nothing is created

#### Scenario: Viewer cannot import or export
- **WHEN** a member with the viewer role posts an import or requests an export
- **THEN** both answer 403

