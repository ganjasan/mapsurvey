## 1. Foundation: models, resolver, settings

- [x] 1.1 `MapStyle` and `MapStyleVersion` in `survey/models.py` (design D1), `SurveyHeader.basemap_pins`, `max_length=50` and no `choices` on the four basemap fields; `BASEMAP_CHOICES` and `default_basemaps()` stay as the preset keys only
- [x] 1.2 Migration `0117_map_styles`: schema + `RunPython` seeding the five presets (Paper ids from `os.environ` with production defaults), reversible
- [x] 1.3 `survey/map_styles/generator.py` — `apply_settings`, `greyscale`, `parse_color`, `MapboxStylesClient` moved from the script; the script imports them; `test_map_style_rendering` still green
- [x] 1.4 `survey/basemaps.py` — `Basemap`, `available_for`, `choices_for`, `resolve`, `table_for`, `usage`, `pin_latest`, `name_of` (design D3, D5)
- [x] 1.5 Settings: `MAPBOX_TILES_URL`, `MAPBOX_ACCOUNT`; remove `MAPBOX_URL`, `MAPBOX_OUTDOORS_URL`, `MAPBOX_PAPER_*`; `.env.example` and `render.yaml` updated; `mapbox` context processor exposes `MAPBOX_STREETS` (url + options) and the token only
- [x] 1.6 Template tag `{% basemap_table org pins %}` in `survey/templatetags/basemaps.py`

## 2. Surfaces read the table

- [x] 2.1 `partials/basemap_layers.html` builds layers from the table (name, url, options); respondent page, editor preview, section map picker, Responses geo map, session detail, layer editor follow (they include it); remove layer_editor's stray `mapboxUrl`
- [x] 2.2 Create wizard `survey_create.html`: provider dict and slug list replaced by the table; labels from it
- [x] 2.3 `public_results.html`: `BASEMAPS` dict replaced by the table for the survey's workspace with the survey's pins; `public_results.py` payload unchanged
- [x] 2.4 Streets-only surfaces (`survey_settings_panel` picker + style preview, legacy `survey_settings.html`, Responses overview thumbnail, Responses map modal) use `MAPBOX_STREETS`
- [x] 2.5 Print: `static_map.py` resolves through `basemaps.resolve` (`_basemap_key` + `basemap_style`); `BASEMAP_STYLES` removed; paper layout keeps the key
- [x] 2.6 `test_no_template_holds_a_mapbox_url` scanning `survey/templates/`

## 3. Pickers, validation, pins

- [x] 3.1 `SurveyHeaderForm`: `default_basemap` choices and `clean_basemaps` from `choices_for(instance.organization)`; settings panel and legacy page render workspace styles after the presets; `basemap_choices` context from the resolver (settings, section picker, public results editor)
- [x] 3.2 Create wizard views (manual and AI) validate `default_basemap` against the workspace's keys
- [x] 3.3 `services.sections.set_map` validates `override_basemap`; `public_results_editor` validates block basemap
- [x] 3.4 Pins: `pin_latest` on the draft → published transition in `services/publishing` and in `publish_draft`; draft copy gets `{}`; archived header gets pins + `basemaps` + `default_basemap`; `DraftCopyKeepsFieldsTest` exclusion
- [x] 3.5 ZIP import maps an unresolvable `style:` key to `streets` with a report line; export unchanged
- [x] 3.6 API v1 / MCP: field descriptions mention `style:<uuid>`; regenerate `reference/api.md` and `reference/mcp-tools.md`

## 4. Library page

- [x] 4.1 `survey/map_style_views.py` + URLs: list (every member), duplicate / rename / delete (POST, owner/admin/editor); `org/map_styles.html` laid out like General; cards with preview tile, base, usage, status chip; HTMX poll while pending
- [x] 4.2 Duplicate: Pro gate `require_feature('map_styles')`, `trial.use` on create, version 1 `pending`, enqueue publish; no Duplicate on Satellite and Topo
- [x] 4.3 Delete: refused with surveys named when used; else `archived_at` + enqueue Mapbox delete; Rename inline
- [x] 4.4 Sidebar: `LIBRARY` group in `app_nav.py`, `_ACTIVE_BY_PREFIX` entries, `_app_sidebar.html` renders the group with `{% pro_badge active_org "map_styles" False %}`; `test_workspace_navigation` updated
- [x] 4.5 PostHog events `map_style_created`, `map_style_deleted` (ids and kind only)

## 5. Celery publishing

- [x] 5.1 `survey/map_styles/tasks.py`: `publish_map_style_version`, `delete_mapbox_style` (`queue='styles'`, `rate_limit='40/m'`, retries, `failed` + `error` on exhaustion); base style cached a day
- [x] 5.2 `CELERY_TASK_ROUTES`; `run_dev.sh` and `render.yaml` worker consume `-Q celery,styles`; `MAPBOX_STYLES_TOKEN` + `MAPBOX_ACCOUNT` on the worker env in `render.yaml` (`sync: false`)
- [x] 5.3 *Try again* on a failed version re-enqueues

## 6. Billing, help, translations

- [x] 6.1 `FEATURES['map_styles']`, `TRIAL_ALLOWANCES['map_styles'] = 2`; billing tests for the registry
- [x] 6.2 Help page `how-to/map-styles.md`, `HELP_LINKS['map_styles']`, link on the library page
- [x] 6.3 New creator strings in every offered catalog (`TranslationCatalogHygieneTest`)

## 7. Tests and wrap-up

- [x] 7.1 `survey/tests/test_map_style_library.py` covering every scenario of the new spec; `UNMAPPED_MODULES` entry while the change is unarchived
- [x] 7.2 Update `test_basemap_providers`, `test_printable_form`, `test_survey_editor`, `test_public_results_page`, e2e `conftest` for the table and 512-px URLs
- [ ] 7.3 Full suite green; `openspec validate --strict`; migration number checked against `origin/master`
- [ ] 7.4 Dev check on :8770: library page, duplicate Paper A (worker publishes), pick it in a survey, respondent page, print frame; screenshots for the owner
- [ ] 7.5 PR into `epic/map-styles`, merge, archive the change in a follow-up PR
