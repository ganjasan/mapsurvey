## Why

A style is a settings document (#542) a creator can shape in the editor (#543); the vision (FE-6) wants it to be a portable object too — exported from one workspace, imported into another, and later the unit of a shared catalogue (v2.0) and of the API/MCP payload (v1.1). Without this a consultancy with three client workspaces rebuilds its house style three times.

## What Changes

- **Export**: `GET /org/<slug>/map-styles/<uuid>/export.json` downloads one JSON file — format name, format version, style name, base, settings — and never a Mapbox id or a workspace reference. Available for workspace styles and for the presets the generator can rebuild (Streets, Paper A, Paper B).
- **Import**: a file field on the library page posts to `/org/<slug>/map-styles/import/`; the document is validated against the format version and normalised through the editor's control schema (so an import can never name a layer, font or sprite); a name already in the library gets a numeric suffix; the result is a workspace style with version 1 `pending`, published like a duplicate.
- Both are Pro (`map_styles`): import counts as creating a style (one trial use), export needs the feature in force.
- The format is documented on the help page as the one a catalogue entry or an API payload will carry.
- Event `map_style_imported`.

## Capabilities

### New Capabilities
- `map-style-import-export`: the document format, export, import with validation and name suffixing, the gates.

### Modified Capabilities
<!-- none: the library page gains two actions; its requirements are unchanged -->

## Impact

- New: `survey/map_styles/io.py`, `survey/map_style_io_views.py`, `survey/tests/test_map_style_import_export.py`.
- Changed: `survey/urls.py`, `org/map_styles.html`, `org/_map_style_cards.html`, help page, locales.
- No model or migration change; no new dependency.
