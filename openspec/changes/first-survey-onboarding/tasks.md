## 1. Data and events

- [x] 1.1 Add `survey_start_default` (CharField, choices `''`/`blank`/`ai`, default `''`) and `agent_access_requested_at` (DateTimeField, null) to `CreatorPreferences`; migration `0097`
- [x] 1.2 `product_events.py`: `AGENT_ACCESS_REQUESTED = 'agent_access_requested'` in the event list; constants for `surface` (`SURFACE_START_BLANK`, `SURFACE_CREATE_PAGE`)
- [x] 1.3 Context processor (or extend an existing creator one) exposing `survey_start_default` to templates from `request.user.preferences` without an extra query on anonymous/respondent pages

## 2. Map start chain

- [x] 2.1 `survey/country_centroids.py`: ISO 3166-1 alpha-2 → (lat, lng) for every assigned code
- [x] 2.2 `survey/map_start.py`: `StartPosition` namedtuple and `suggest_start_position(request, *, browser=None)` with the rungs `browser` → `org_survey` → `country` (`CF-IPCountry` under `CLOUDFLARE_TRUSTED`, else `Accept-Language` region) → `world`; never raises, one query
- [x] 2.3 Tests: each rung, untrusted edge header ignored, unknown code → world, malformed browser values ignored, `Accept-Language` without region → world

## 3. Blank creation and the create page

- [x] 3.1 Extract `_create_blank_survey(request, *, name, languages, start, surface, map_source)` from `editor_survey_create`'s manual branch (header, owner collaborator, section S1, `SURVEY_CREATED`); the manual branch calls it with `surface='create_page'` and the posted `map_source` (`creator` when `map_touched=1`)
- [x] 3.2 `editor_survey_create_blank` (POST only, editor role): name `_('Untitled survey')`, languages from the UI language, start from the chain with posted `map_lat/lng/zoom` as `browser`; writes `survey_start_default` when `remember=1`; redirects to the editor; URL `editor/surveys/new/blank/`
- [x] 3.3 Create page: view passes `initial_lat/lng/zoom/map_source` from the chain; template's first `setView` uses them, hidden `map_source` field; `from=start` swaps "Skip and start from scratch" for a "Start another way" link
- [x] 3.4 Create page geolocation: replace the on-load request with a `permissions.query` probe (silent read only on `granted`); hint line "Use my location" above the map when `map_source` is `country`/`world`; no Permissions API → no silent read
- [x] 3.5 `_start_survey_generation` passes `map_source` through to the task; `tasks.py` sets `map_source='brief'` on `survey_created` when the geocoded location replaced the form position
- [x] 3.6 Tests: blank endpoint (survey, section, collaborator, redirect, languages per UI language incl. unsupported, browser position, GET creates nothing, viewer refused, `remember=1`), "Untitled survey" passes `url_name_validator` in every `LANGUAGES` catalog, create page initial centre and `map_source` field, `from=start` rendering, manual action's `surface`/`map_source`

## 4. Start page

- [x] 4.1 `editor_survey_start` GET (editor role): three cards, `ai_available`, `welcome` escape, current default with Clear; POST handles `action=ai` (+`remember`) → write default, redirect to create page with `from=start`; `action=clear`
- [x] 4.2 Template `editor/survey_start.html` extending `editor/editor_base.html`; card markup, "Always start this way" checkbox on the two actionable cards, disabled AI card copy, *soon* badge on the agent card; styles in the editor CSS "create" block; phone layout
- [x] 4.3 Start page JS: *Start from scratch* submit handler — `permissions.query`; on `prompt` ask with a 3 s ceiling; fill hidden `map_lat/lng/zoom` on success; submit either way
- [x] 4.4 `views.editor`: empty-organization redirect → `editor_survey_start` + `?welcome=1`
- [x] 4.5 Dashboard (`editor.html`): "+ New Survey" rendered by `survey_start_default` (link / link / POST form); ⋯ menu "Start another way…"
- [x] 4.6 Tests: start page rendering per role and provider state, welcome escape, default set via AI card and via blank form, clear, dashboard button per default, empty-org redirect target, `?dashboard=1` still suppresses

## 5. Agent access teaser

- [x] 5.1 `editor_account_mcp` (login required) GET/POST; POST sets `agent_access_requested_at` once and emits `agent_access_requested` once; URL `editor/account/mcp/`
- [x] 5.2 Template `editor/account_mcp.html`: three paragraphs, example prompt, button / confirmation state
- [x] 5.3 Menu entries: "AI agents & MCP" + *soon* badge in the account menu of `base.html` AND `editor/editor_base.html`; "Connect your AI agent" in `editor/partials/_help_menu.html`
- [x] 5.4 Tests: page renders, interest recorded once with one event, anonymous redirect, both bases show the menu item, help menu shows the link

## 6. Localisation, changelog, docs

- [x] 6.1 Every new `{% trans %}`/`_()` string in all offered creator catalogs (de, fr, es, pt, pl, id, nl, it, et, fi) plus ru — appended by hand like PR #274, `compilemessages`; `TranslationCatalogHygieneTest` is what enforces it
- [x] 6.2 Changelog entry `survey/changelog/<date>-ways-to-start.html` (`kind: new`, `link: editor_survey_start`)
- [x] 6.3 `CLAUDE.md`: a paragraph on the start page, `survey_start_default`, `map_start` and the agent page URL contract with #306; note on #306 that the URL name and menu entries exist
- [x] 6.4 Full `./run_tests.sh survey`: 2583 tests, one failure (a translation collision in the new entries, fixed), `TranslationCatalogHygieneTest` green afterwards
- [x] 6.5 Help centre: `start-here/create-a-survey.md` and `start-here/index.md` follow the start page, `troubleshooting/ai-draft-failed.md` names the way back, new `how-to/choose-how-to-start.md` (cards, default, where the map opens) linked from the start page through `HELP_LINKS["ways_to_start"]`; `npm run build` validates every internal link
