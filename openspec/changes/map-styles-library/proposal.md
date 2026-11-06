## Why

Base maps are five slugs hard-coded in `BASEMAP_CHOICES`, five tile URLs in settings, a second copy of both in the create wizard and the public results page, and a third table in the print module. A client who wants a map that looks like their own cartography gets a developer session in Mapbox Studio and one more slug (#534, Paper A and Paper B on 2026-11-06). The Map styles epic (#545, Vision in `openspec/docs/vision/map-styles.md`) turns a style into a workspace object; this change (#542) lays the foundation: the data model, the one resolver every surface reads, the presets as rows, the library page in the sidebar, and the Pro gate. The rendering path is settled by ADR 0001 (hybrid): hosted raster at 512 px everywhere a respondent or reader looks, immutable hosted styles, one Mapbox style per saved version.

## What Changes

- **Two models.** `MapStyle` (workspace-owned, or a system preset when it has no workspace) and `MapStyleVersion` (an immutable published version: settings document, provider, Mapbox style id or raw tile URL, status). Streets, Satellite, Topo, Paper A and Paper B become system rows seeded by the migration; the `MAPBOX_URL`, `MAPBOX_OUTDOORS_URL`, `MAPBOX_PAPER_STYLE`, `MAPBOX_PAPER_B_STYLE` settings go. One template `MAPBOX_TILES_URL` (512-px tiles, #522) and the tokens stay.
- **One resolver**, `survey/basemaps.py`: a basemap key is a system key (`streets`, `satellite`, `topo`, `paper`, `paper_b`) or `style:<uuid>` of a workspace style. Every surface that draws a base map — the eight Leaflet surfaces, the print frame, the public results page — resolves keys through it and renders from one provider table; no template holds a tile URL for a Mapbox style any more. Every Mapbox layer is 512-px with `tileSize: 512, zoomOffset: -1`.
- **Survey fields keep their shape**: `SurveyHeader.basemaps` / `default_basemap`, `SurveySection.override_basemap`, `PublicResultsBlock.basemap` stay strings, widened to 50 chars and without DB `choices`; validation moves to the resolver. **BREAKING** for nothing stored: existing slugs are the system keys.
- **Version pinning** (ADR decision 2, vision FE-7): `SurveyHeader.basemap_pins` records, per referenced workspace style, the version a published survey shows. Publishing writes the pins; a draft copy clears them and shows the latest version.
- **The library page** `/org/<slug>/map-styles/` in a new *Library* sidebar group: cards for the five presets and the workspace's styles (preview, base, "used in N surveys"), *Duplicate* (Pro), *Rename*, *Delete* (refused while a survey uses the style). No editor yet (#543): a duplicate is the same settings under a new name, published to Mapbox as its own style by a Celery task.
- **Publishing moves into the app**: the generator of `scripts/mapbox_style_publish.py` becomes `survey/map_styles/generator.py`; a Celery task on its own queue (the Styles API allows 50 writes/min per account) creates the Mapbox style, deletes it when a style is deleted, and marks the version `ready` or `failed`. The script keeps working for the presets.
- **Pro gate** `map_styles` in `billing/features.py`: duplicating (creating) a style needs it; using any style already in the library — system or workspace — is free. Trial allowance: 2 styles.
- **Survey settings** list workspace styles after the presets; section override and public results block pickers do the same; ZIP import maps a `style:` key that does not exist in the importing workspace to `streets` with a report line; the API keeps its string fields.
- Help centre page *Map styles* and the `map_styles` help link; translations for the new creator strings in every offered catalog.

## Capabilities

### New Capabilities
- `map-style-library`: workspace map styles and their versions, the resolver and the one provider table, the library page and its actions, the Pro gate, version pinning, Mapbox publishing in Celery.

### Modified Capabilities
- `basemap-providers`: the provider table comes from the library, not from per-style settings; Topo's style is the preset row's id; all Mapbox tiles are 512 px from `MAPBOX_TILES_URL`.
- `public-results-page`: a map block's basemap is any key the resolver knows for the survey's workspace, not only `streets`/`satellite`/`topo`.
- `workspace-navigation`: a *Library* group with *Map styles* between *Integrations* and *Workspace*, carrying the `map_styles` Pro mark.

## Impact

- New: `survey/basemaps.py`, `survey/map_styles/` (`generator.py`, `tasks.py`), `survey/map_style_views.py`, `survey/templates/org/map_styles.html`, `survey/templatetags/basemaps.py`, migration `0117_map_styles`, `survey/tests/test_map_style_library.py`, help page `how-to/map-styles.md`.
- Changed: `survey/models.py` (four fields, two models), `mapsurvey/settings.py`, `survey/context_processors.py`, `survey/app_nav.py`, `partials/_app_sidebar.html`, `partials/basemap_layers.html` and the seven other map surfaces, `survey/print/static_map.py`, `survey/editor_forms.py`, `survey/editor_views.py` (create, settings, section picker), `survey/services/sections.py`, `survey/public_results*.py`, `survey/serialization.py`, `survey/versioning.py` (pins on publish and draft), `billing/features.py`, `survey/help_links.py`, `scripts/mapbox_style_publish.py` (imports the generator), `survey/urls.py`, `survey/locale/*`.
- Tests touched: `test_basemap_providers`, `test_printable_form`, `test_survey_editor`, `test_public_results_page`, `test_workspace_navigation`, `test_test_suite` (lineage), e2e `conftest`.
- Settings removed: `MAPBOX_URL`, `MAPBOX_OUTDOORS_URL`, `MAPBOX_PAPER_STYLE`, `MAPBOX_PAPER_URL`, `MAPBOX_PAPER_B_STYLE`, `MAPBOX_PAPER_B_URL` (none is set on Render; the defaults are what production runs). Added: `MAPBOX_TILES_URL`, `MAPBOX_STYLES_TOKEN` on the worker, `MAPBOX_ACCOUNT`.
- Celery: new queue `styles` with `rate_limit='40/m'`; the worker command must consume it (same worker, extra `-Q`).
- Mapbox account: one style per workspace style version; deletes follow style deletion after a grace period.
- Not in this change: the style editor and previews (#543), import/export (#544), the API/MCP style endpoints (v1.1), the What's new card (ships with the epic).
