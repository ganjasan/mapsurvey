## Context

Inventory (2026-11-06, this worktree): basemap selection lives in four fields — `SurveyHeader.basemaps` (JSON list of slugs), `SurveyHeader.default_basemap`, `SurveySection.override_basemap`, `PublicResultsBlock.basemap` (CharField 20, `choices=BASEMAP_CHOICES`) — and is read by `partials/basemap_layers.html` (included by the respondent page, editor preview, section map picker, Responses geo map and session detail, layer editor), by three templates with their own provider dicts (create wizard, public results page, `survey_settings_panel` + legacy settings page + Responses overview thumbnail + map modal, all streets-only), by `survey/print/static_map.py::BASEMAP_STYLES`, by `SurveyHeaderForm.clean_basemaps`, `services.sections.set_map`, `public_results_editor`, `serialization` (ZIP), `versioning.clone_survey_for_draft` / `publish_draft` (hand-written field lists), `cloning` (plain fields), `ai/materialize.header_overrides_from_form`, API v1 `SurveyPatchIn`/`SurveyDetailOut` (strings), MCP `update_survey`. Tile URLs come from five settings through the `mapbox` context processor. ADR 0001 fixes the path: hosted raster 512 px, immutable hosted styles, MapLibre only in the editor (#543).

Constraints: one developer; `basemap-providers` forbids volunteer tile hosts and demands one provider table; `#329` taught that hand-written copy lists lose fields, so every new survey field is added to `clone_survey_for_draft`, `publish_draft` and the archived-header creation in the same commit; migrations on `epic/map-styles` must be renumbered against `master` before the epic PR.

## Goals / Non-Goals

**Goals**
- A style is a row a creator can see, name, duplicate and delete; the presets are rows too.
- One resolver and one provider table; a template never names a Mapbox style again.
- 512-px tiles everywhere Mapbox is drawn (#522 lands here).
- Publishing to Mapbox is a background task bounded by the account's write limit.
- Pinning exists so #543 can save new versions without touching live surveys.

**Non-Goals**
- Editing settings in the UI (#543), import/export (#544), API/MCP endpoints for styles (v1.1), the shared catalogue (v2.0).
- Styling satellite; a satellite row exists so the picker and print treat it like any other key, but it cannot be duplicated.
- Removing `MAPBOX_SERVER_TOKEN` or changing the print pipeline beyond where it looks up the style id.

## Decisions

### D1. Two models, versions immutable
`MapStyle(uuid, organization NULL=system, key '' or system slug, name, base '' | 'mapbox/streets-v12', created_by, created_at, updated_at, archived_at)` and `MapStyleVersion(style, number, settings JSON, provider 'mapbox'|'xyz', mapbox_style_id, tile_url, static_style, attribution, max_zoom, status pending|ready|failed, error, created_by, created_at)`, unique `(style, number)`. A version row is never updated after `ready` except to be deleted with its style. `MapStyle.latest_ready()` is what surfaces resolve to unless pinned. Alternative — one model with a mutable `mapbox_style_id` — rejected: ADR 0001 measured in-place updates leaving raster tiles stale for hours, and #543 needs a history to pin.

### D2. Keys stay strings in the survey fields
`basemaps`, `default_basemap`, `override_basemap`, `PublicResultsBlock.basemap` keep their types; `max_length` becomes 50 and the DB `choices` go (they only ever validated forms and the admin). A workspace style is referenced as `style:<uuid>`; system presets keep `streets`, `satellite`, `topo`, `paper`, `paper_b`, so no stored value changes and ZIP, API, MCP, cloning and the paper layout JSON carry keys exactly as today. Alternative — foreign keys — rejected: the JSON list cannot hold one, four fields would diverge, and every reader above would need a join; the resolver already answers "what does this key mean for this workspace".

### D3. One resolver, one table
`survey/basemaps.py`: `Basemap` (key, name, kind, provider, tile_url with `{accessToken}` left for the client, `tile_size`, `zoom_offset`, `max_zoom`, `attribution`, `static_style`, `style`, `version`), `available_for(org)` (presets, then the workspace's non-archived styles with a ready version), `choices_for(org)`, `resolve(key, org, pins=None)`, `table_for(org, pins=None)` (the JSON the templates get), `usage(org)` (`{style_uuid: n surveys}` over headers, sections and blocks of the workspace's surveys), `pin_latest(survey)`, `name_of(key, org)`. Template tag `{% basemap_table org pins %}` emits the table once per page; `basemap_layers.html` builds Leaflet layers from it; the create wizard and `public_results.html` drop their own dicts and read the same tag; the four streets-only surfaces read `MAPBOX_STREETS` (url + Leaflet options) from the `mapbox` context processor, which is `table_for(None)['streets']`. Tile options are part of the table entry (`tileSize`, `zoomOffset`, `maxZoom`, `attribution`), so #522's 512-px shape cannot drift between surfaces.

### D4. Settings: a template, not five URLs
`MAPBOX_TILES_URL = 'https://api.mapbox.com/styles/v1/{style}/tiles/512/{z}/{x}/{y}@2x?access_token={accessToken}'` (env-overridable; an override still saying `256` works because the table carries `tileSize` from the URL). Preset rows hold `mapbox/streets-v12`, `mapbox/outdoors-v12`, the two Paper ids and, for satellite, the Esri XYZ template with `static_style = 'mapbox/satellite-streets-v12'`. The migration seeds the rows reading `MAPBOX_PAPER_STYLE` / `MAPBOX_PAPER_B_STYLE` from `os.environ` with the production ids as defaults, then those settings are deleted from `settings.py`. Render has none of them set (checked 2026-11-06), so nothing changes in production.

### D5. Pins: written at publish, cleared on draft
`SurveyHeader.basemap_pins` JSON `{style_uuid: version_number}`. `pin_latest(survey)` is called by `services.publishing` on the draft → published transition and by `versioning.publish_draft` after settings are copied; `clone_survey_for_draft` writes `{}` on the draft so Build and the editor preview show the latest version; the archived header gets the canonical's pins (and, fixing a gap, its `basemaps` / `default_basemap`). `resolve` honours a pin whenever the key is a workspace style and the pin names a ready version; otherwise latest. In this change only the migration and *Duplicate* create versions, so pins always equal 1; the tests create a second version directly to prove the rule.

### D6. Library page and actions
`survey/map_style_views.py`, URL `org/<slug>/map-styles/` (`org_map_styles`, every member), `.../duplicate/<uuid>/`, `.../<uuid>/rename/`, `.../<uuid>/delete/` (POST, roles owner/admin/editor). The page is laid out like Members/General (`container`, `max-width 720px`). A card: preview (one 512-px tile at zoom 12 over the workspace's start position from `map_start.suggest_start_position`'s `org_survey` rung, else Copenhagen — one Static Tiles request per card, cached by the browser), name, "Preset" or base, "Used in N surveys", status chip while `pending` or `failed`, actions. The page polls itself every 3 s with HTMX while any version is pending, as the import-jobs card does. *Duplicate* on Satellite and Topo is absent (`base == ''`: the generator knows `streets-v12` layer ids only). *Delete* on a style with usage > 0 renders a 409 message naming up to five surveys and does nothing; on an unused style it sets `archived_at` and enqueues the Mapbox delete for each ready version.

### D7. Publishing in Celery
`survey/map_styles/generator.py` is `apply_settings`, `greyscale`, `parse_color`, `MapboxStylesClient` moved verbatim from the script (the script imports them, so its tests keep passing). `survey/map_styles/tasks.py::publish_map_style_version(version_id)` — `@shared_task(bind=True, rate_limit='40/m', queue='styles', max_retries=3)`: fetch base (cached a day), `apply_settings`, `create` with name `mapsurvey/<org slug>/<style uuid>/v<n>`, write `mapbox_style_id`, `status='ready'`; failure → `status='failed'`, `error`, PostHog exception. `delete_mapbox_style(style_id)` is a second task with the same queue. `MAPBOX_STYLES_TOKEN` is read by the worker only; `MAPBOX_ACCOUNT` names the account (`artemkonuchov`). `CELERY_TASK_ROUTES` sends both to `styles`; the worker command in `render.yaml` and `run_dev.sh` adds `-Q celery,styles`. Alternative — publishing in the request — rejected: 0.9 s per create and a 50/min account-wide limit that one classroom could hit.

### D8. Pro gate and trial
`FEATURES['map_styles']` ("Your own map styles"), `TRIAL_ALLOWANCES['map_styles'] = 2`. `require_feature('map_styles', org)` on the duplicate view, `trial.use(org, 'map_styles', user)` at the moment the row is created, `{% pro_badge active_org "map_styles" False %}` on the sidebar row and the Duplicate button. Using a style in a survey is never gated: a lapsed workspace keeps the maps its respondents see (the operator-entry rule).

### D9. Pickers and validation
`choices_for(org)` replaces `BASEMAP_CHOICES` in `SurveyHeaderForm` (which gets the organisation from its instance), the settings panel, legacy settings page, section map picker, public results editor and the create wizard; `clean_basemaps` and the three view-level validations check membership in the workspace's keys. `services.sections.set_map` validates `override_basemap` the same way (today it trusts model choices). ZIP import: a key the importing workspace cannot resolve becomes `streets` and a line in the import report, like an unresolvable visibility rule. Draft copies, duplicates and paste keep keys as they are.

### D10. What the generated reference docs need
API v1 and MCP schemas keep `basemaps: List[str]` and `default_basemap: str`; their descriptions gain "a preset key or `style:<uuid>` of a workspace map style". `scripts/build_api_reference.py` / `build_mcp_reference.py` are re-run so `ApiReferenceFreshnessTest` and `test_reference` stay green.

### D11. Translations and help
New creator strings go into every offered catalog by hand (`TranslationCatalogHygieneTest`); `help/src/content/docs/how-to/map-styles.md` describes the library as it is in this change and is linked from the page through `HELP_URL.map_styles`.

## Risks / Trade-offs

- [`basemaps__contains` over JSON lists for usage counts is slow on a big workspace] → counts are computed once per page render over the workspace's surveys only (hundreds of rows at most); a cached column is #543's problem if it ever shows.
- [A worker that does not consume `styles` leaves versions `pending` forever] → the page shows the chip with the time pending; `run_dev.sh`, `render.yaml` and a test on `CELERY_TASK_ROUTES` + the worker command line are in this change.
- [Removing five settings breaks a self-hosted instance that set them] → release note in the epic PR; the migration reads `MAPBOX_PAPER_STYLE` / `_B_STYLE` from the environment once, so a set value survives as the preset row.
- [`max_length` 20 → 50 and dropped `choices` need an `AlterField` on three tables] → metadata-only on PostgreSQL (`varchar` widening is a catalogue change), no rewrite.
- [Hand-written copy lists in `versioning.py` miss `basemap_pins`] → `DraftCopyKeepsFieldsTest` compares every concrete field; the pins exclusion is explicit there.
- [The Esri preset has no settings and no Mapbox id] → `provider='xyz'`, `tile_url` set, generator never touches it; print uses `static_style`.
- [Migration number collides with `master`] → check `origin/master` before the PR; renumber at the epic merge if needed.

## Migration Plan

One migration `0117_map_styles`: create the two models, `AlterField` the four basemap fields (`max_length=50`, no choices), add `basemap_pins`, then `RunPython` seeding five `MapStyle` rows (`organization=None`, keys) each with version 1 `ready`. Reverse deletes the rows. Deploy: migrate (additive), worker restart with the new queue. Rollback: revert the deploy; the migration's reverse is safe because no survey field changed shape.

## Open Questions

- Should *Rename* be free on presets? No — presets are read-only; a workspace renames its duplicate. Decided.
- Preview frame for a workspace with no positioned survey: Copenhagen (the demo) for now; the editor (#543) lets the creator pick.
