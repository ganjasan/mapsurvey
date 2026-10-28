# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Docker (recommended)
docker-compose up --build              # Start all services
docker-compose up db                   # Start only PostgreSQL/PostGIS

# Local development (venv in ./env — Python 3.12; the image is python:3.12-slim, Django 5.2 LTS)
source env/bin/activate                # Activate virtual environment
pipenv install                         # Install dependencies (Pipfile — there is no requirements.txt)
# Faster equivalent for a fresh venv: uv venv --python 3.12 env && pipenv requirements --dev > /tmp/r.txt
#                                     && uv pip install --python env/bin/python -r /tmp/r.txt
# Branches from before change python312-django52-upgrade need a 3.9 venv (kept as ../Mapsurvey/env39).
# Deprecation gate (run once per Django bump): python -W error::django.utils.deprecation.RemovedInDjango60Warning
#   -W error::DeprecationWarning:survey -W error::DeprecationWarning:mapsurvey manage.py test survey
python manage.py migrate               # Apply database migrations
python manage.py runserver             # Start development server (port 8000)
python manage.py createsuperuser       # Create admin user
python manage.py collectstatic         # Collect static files

# Testing (requires running PostGIS on port 5434)
./run_tests.sh survey                  # Run all survey app tests
./run_tests.sh survey -v2              # Verbose output
./run_tests.sh survey.tests.test_public_stories   # One capability's tests
./run_tests.sh survey.tests.test_smoke.SmokeTest  # One test class
```

## Parallel worktrees (port isolation)

`run_dev.sh`, `run_tests.sh`, and `run_e2e.sh` derive every host port from a single
`PORT_OFFSET` so multiple worktrees can run dev + tests at the same time without
colliding. To set up a worktree: `cp .env.ports.example .env.ports` and pick a unique
offset (keep the registry in that file current). Ports = base + offset
(PostGIS `5434`, Redis `6379`, web `8000`). `COMPOSE_PROJECT_NAME` isolates the docker
stack per worktree. Offset `0` reproduces the original ports. `.env.ports` is gitignored.

## Testing

Tests use Django's built-in test framework with PostGIS. Django automatically creates a separate `test_mapsurvey` database.

**Prerequisites**: none — `run_tests.sh` starts the PostGIS and Redis containers itself and waits
for both. Redis is not optional: `settings.py` falls back to `redis://localhost:6379/1` when
`REDIS_URL` is unset, so on a machine running several projects the suite would otherwise connect to
whichever project owns that port and write into its database. `CACHES` sets `IGNORE_EXCEPTIONS`, so
that goes wrong silently rather than failing loudly.

**Full suite**: `./run_tests.sh survey billing api mcp newsletter`. One area: a label
(`survey.tests.test_public_stories`, `survey.tests.test_public_stories.SeedStoryTest`,
`api.tests.test_v1_data`, `billing`).

**Run defaults (change `test-suite-speed`, #272)**: `run_tests.sh` always passes `--noinput`
and runs `--parallel auto` (one worker per core) unless you pass `--parallel` yourself;
`TEST_PARALLEL=1` for `pdb` or a readable traceback order. `KEEPDB=1` adds `--keepdb` — opt-in,
because Django does not re-migrate kept parallel clones, so after a new migration the workers
would test the old schema. `TEST_RUNNER` (`mapsurvey/test_runner.py`) applies to every
`manage.py test`: MD5 password hasher, a temporary `MEDIA_ROOT` (tests never write into
`mediafiles/`), and a Redis database per parallel worker (`1 + worker id`, capped at 14
workers) — django-redis `cache.clear()` is `FLUSHDB`, so a shared database would let one
worker wipe another's rate-limit counters. `tblib` (dev package) is required: without it a
failure inside a worker aborts the whole run with a `TypeError` and a cascade of unrelated
`IntegrityError`s. Views leave `translation.activate()` behind, so the runner resets
the language to `LANGUAGE_CODE` before every test (wrapping `SimpleTestCase._pre_setup`). A test that only passes serially is relying on
another test's state; fix the test, never pin the suite to one process.

**Test location — one module per capability (change `split-survey-tests`, #273)**: the survey
app's tests are the package `survey/tests/`, with `test_<capability>.py` for each folder under
`openspec/specs/` (`-` → `_`) and shared fixtures in `survey/tests/helpers.py`. A change adds its
tests to the module of the capability its spec delta touches; a NEW capability adds its own
module, so parallel branches touch different files. `SpecTestLineageTest`
(`test_test_suite.py`) fails when a module names no spec and is not in `UNMAPPED_MODULES` (with
a reason), or a spec has no module and is not in `SPECS_WITHOUT_SURVEY_TESTS` — both lists may
only shrink, and the stale-entry test enforces it. `api/tests/`, `billing/tests/` and
`mcp/tests/` follow the same one-module-per-capability rule.

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.

## Load testing

`loadtest/lecture-burst.js` (k6) reproduces a lecture-hall burst — N students opening the
same map survey at once. It does **not** reproduce locally (a dev machine is far faster
than the 0.5 CPU Render Starter instance previews run on; production is on Standard,
1 CPU / 2 GB, since the 2026-09-15 memory-limit incident), so run it against a Render PR
preview, never production. Previews are opt-in (`previews.generation: manual` in
`render.yaml`): put `[render preview]` in the PR title to get one; it is deleted after a day
without new commits. Seed the preview's empty database first with
`python manage.py seed_loadtest_survey`. See `loadtest/README.md`.

## Architecture Overview

This is a Django-based geospatial survey platform using PostGIS for storing geographic data (points, lines, polygons).

### Project Structure

- `mapsurvey/` - Django project settings and root URL configuration
- `survey/` - Main application with all business logic

### Core Data Model Hierarchy

```
Organization
└── SurveyHeader (survey definition)
    ├── SurveySection (logical groupings with map position)
    │   ├── Question (supports 12+ input types including GIS)
    │   └── OptionGroup → OptionChoice (reusable choice sets)
    └── SurveySession (user's survey attempt)
        └── Answer (stores responses with GIS geometry fields)
```

### Key Patterns

**Dynamic Form Generation**: `SurveySectionAnswerForm` in `survey/forms.py` dynamically builds form fields based on question `input_type`. Each type maps to specific Django fields and custom Leaflet widgets for GIS input.

**Question Types**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime`, `point`, `line`, `polygon`, `image`, `html`

**Creator rich text (`Question.subtext`, `SurveySection.subheading`, `SurveyHeader.thanks_html`)**:
everything a creator writes in their own words is authored in Quill and rendered to respondents as
markup. All of it is unbounded `TextField` and all of it passes `survey/html_sanitize.py` on the way
in — `QuestionForm.clean()`, `SurveySectionForm.clean_subheading()`, the translation savers in
`editor_views.py`, `serialization._import_rich_text()` (ZIP import, which is also how AI generation
writes), and `editor_question_preview_live` so the preview equals what a save keeps. **A new way to
write these fields must go through the same helper**; the allow-list is what stands between a
creator and stored XSS on every respondent.

Use `coerce_creator_html`, not `sanitize_creator_html`, anywhere a value might not be from an
editor. These fields hold plain text from before the editors existed (old rows, old ZIPs, AI
drafts), and `nh3` would read "takes <5 minutes" as an unknown tag and delete it; `coerce_` escapes
what carries no creator markup and sanitizes what does. Migration `0056` did the same one-off pass
over the rows already in the database.

The **Formatted Text block (`html`)** is the extreme case: it collects nothing and its `subtext` IS
the whole body, rendered `|safe` in `html_text.html`. `Question.name` for `html` and `image` is an
editor-only label that never reaches the respondent (see the `question-subtext` spec).

**Embedding (`survey/embedding.py`, change embed-surveys, #284)**: a published survey can be framed by
another site. `check_survey_access` calls `mark_embeddable`, `SurveyEmbedMiddleware` turns the mark into
`Content-Security-Policy: frame-ancestors …` (from `SurveyHeader.embed_allowed_hosts` on the canonical
row; empty = `*`) and drops `X-Frame-Options` on that response only — the editor, landing and every 404
keep `SAMEORIGIN`. Cross-site cookie attributes are OPT-IN and off in production: `CROSS_SITE_COOKIES=1`
makes the session and CSRF cookies `SameSite=None; Secure` and `PartitionedCookieMiddleware` appends
`Partitioned`. They were on from 2026-10-13 to 2026-10-22 and cost nine days of answers (#388): the
Facebook/Instagram in-app browsers on iOS keep no `Partitioned` cookie, so every section POST failed CSRF,
and Chromium creators ended up with two `csrftoken` cookies (Django reads the last, `document.cookie`
readers the first). With the switch off the same middleware sweeps the stale partitioned pair from
browsers that still send it. A framed survey keeps its session through the cookie-less carrier below
instead — never turn the switch back on for embeds. The respondent page adds `MS-Embedded: 1` to its HTMX
calls when framed, which is how the final redirect stays on the in-frame thanks page (`?next=`) instead of
navigating the frame to `redirect_url`. The Share page hands out the snippet (`snippet_html`), `/oembed/`
describes it for platforms that do oEmbed discovery, and `/embed.js` (served by a view so the path never
changes) grows the host's iframe from the height messages the page posts. Safari and every iOS browser keep
no cookies inside a third-party frame, so `EmbedSessionMiddleware` (the project's SessionMiddleware) lets a
framed page carry its session key itself — `X-MS-Session` header, `ms_sid` form field with a same-host
Origin, one-time `ms_h` handoff on redirects — only under `/surveys/`, only without a session cookie, never
for a signed-in session, with CSRF still checked (the secret rides in the session). A new respondent view
needs nothing: the mark happens in access control and the carrier in middleware; a new full-page respondent
FORM needs `{% embed_session_field %}` next to its `{% csrf_token %}`.

**Reference overlay layers (`SurveyMapLayer`, kill switch `MAP_REFERENCE_LAYERS`)**: creator-uploaded
GeoJSON rendered read-only beneath answer geometry on four surfaces — the respondent map, the editor
preview, the Responses **Map pane**, its **Overview thumbnail** and the per-response **map modal**
(the 200-px drawer thumbnail stays bare). One styling source: `partials/ref_layer_factory.html` (`window.RefLayerFactory.build`)
is included before any consumer; `partials/reference_layers.html` (respondent) and
`editor/partials/analytics_geo_map.html` (Responses) only fetch and place what it builds. Metadata
comes from `survey/layers.py::build_map_layers_metadata`, geometry only from the gated endpoint
`survey_layer_geojson` — never inlined. That endpoint admits any collaborator with the `viewer`
role or above in every survey status (a closed survey is where responses get read); outsiders
still go through `check_survey_access`, which is deliberately untouched. On Responses, layers are
non-interactive whatever `show_popups` says, ignore per-section `hidden_layers` (the map
aggregates all sections), and make the Map pane render even with zero geo answers. On the Map
pane they are `reference` slots of the `LayerManager`, listed in a titled group beneath the
answer layers in the Layers panel (own pane each, so stacking = panel order, never fetch order);
order, visibility and opacity persist in `localStorage['rv2RefLayers:<uuid>']` — browser-only,
never the model. Cap: `MAX_LAYERS_PER_SURVEY = 10`.

**Layer memory rules (change `layer-memory-diet`, after the 2026-09-15 memory-limit incident)**:
`SurveyMapLayer.geojson` is up to 10 MB of text per row, and a gunicorn worker keeps the RSS of
its largest request for life. The text is stored gzip-compressed in `geojson_gz` (a third of the
bytes in the row, in the worker and on the wire); `geojson` is a property that decompresses on
read and compresses on write, so readers and writers (including `create(geojson=…)`) keep the
text API — but `.defer()`, `update_fields` and `.values()` name `geojson_gz`. The gated endpoint
hands the stored bytes to a client that sends `Accept-Encoding: gzip` (every browser and
`fetch()`) with `Content-Encoding: gzip` and decompresses only for one that does not. So
`layers_for()`, `question_layers_for()` and every layer `get_object_or_404` in editor/object views
DEFER `GEOMETRY_TEXT_FIELDS`; the only readers of the text are the gated endpoint
(`_gated_layer(with_geojson=True)`), `download_data` and the ZIP export
(`layers_for(survey).defer(None)`). `question.layer` cannot defer through the FK, and a
full instance's `save()` writes the text back — on respondent and Responses paths use
`layers.layer_lite(question)`. Property names for the editor's pickers are the stored
`SurveyMapLayer.property_names`, written by `rebuild_layer`; never parse the GeoJSON to list
them. Workers recycle after `GUNICORN_MAX_REQUESTS` (+ jitter) requests, and the worker class is
`mapsurvey.gunicorn_workers.DrainingThreadWorker`, NOT stock `gthread`: gthread drops the
connections it accepted in its last loop iteration when it recycles or gets a deploy's SIGTERM
(one 502 per recycle on 2026-09-16); the draining worker stops accepting first and serves what it
holds. `scripts/gunicorn_recycle_check.py` is the reproduction — run it against both classes after
touching the gunicorn command line or bumping gunicorn. The `LayerMemoryDietTest` query-capture
tests fail if a page starts selecting the column again.

**Layer objects (`LayerObject`, `LayerObjectAsset`; change `overlay-features`)**: a layer is a
container of objects — key, title, category, rich-text description, link, one-part geometry,
raw imported properties, ordered attachments (image/audio/document/video files on the PUBLIC
media tier under random `layer_assets/<uuid>` keys, or YouTube/Vimeo embeds). `SurveyMapLayer.geojson`
is a CACHE derived from them (`survey/layers.py::rebuild_layer`, reserved `_key/_title/_category/
_has_content/_cover` properties) — never edit it as a source; `geojson_legacy` holds the FD-1 text
until one release after migration `0068` and then goes. Layers are owned by the CANONICAL survey
and borrowed by draft copies and archived versions through `layers_for()`/`layer_owner()`; nothing
copies them, so an object edit on a published survey is live for respondents (the object editor
says so in a banner). The object editor is a full page, `/editor/surveys/<uuid>/layers/<id>/edit/`
(`survey/layer_object_views.py`, `js/layer_editor.js`), with three ways in — draw, import GeoJSON,
import CSV — plus content CSV and photo batches matched by key, then title. Per-object cards for
respondents come from `survey_layer_object` under the same gate as the layer endpoint.

**Objects on the map (`layer_objects`) and `thumbs`**: `layer_objects` is a question type bound to
one layer (`Question.layer`, PROTECT — the settings card refuses to delete a bound layer and names
the question); `min_objects` replaces `required`. **Sub-questions are the one mechanism** for "ask
about an object on the map", shared by geo questions and `layer_objects` (`PARENT_TYPES`), with two
entry points into the same modal: the *Sub-questions* section inside the question modal and the
"+ Add Sub-question" button under the question. A geo question with no sub-questions is a normal
state — hint, never block. Respondent side = variant A: the panel list (`partials/layer_objects_block.html`)
is navigation; a row or a feature opens the SAME Leaflet popup respondent-placed features use, with
the object card + the sub-question form + ✓, and nothing opens while a draw/crosshair mode is
active. Answers about objects are rows on the sub-questions with `Answer.layer_object` set (partial
unique per session/sub-question/object) and NEVER `parent_answer_id`; they post as `obj__<key>__<code>`
fields. `thumbs` (👍/👎) is a choice type with the fixed `THUMBS_CHOICES` (`1=up`, `0=down`), so
every choice consumer works unchanged. Aggregates on every read surface come from one place,
`survey/object_stats.py`. Variant B (object card in the panel, geo popups moved there too) is
deferred as a future alternative view — do not reintroduce it ad hoc.

**Marker icons (`Question.icon_class`)**: two value forms — a Font Awesome 5 class (`fas fa-bus`,
legacy `fa fa-bus` and pasted Pro classes pass through untouched) and a map-set name
(`maki:bus`, `temaki:bench`, drawn as `<svg><use>` from the sprites in `survey/assets/img/`).
**Never build icon markup by hand**: on the server use `{% marker_icon value color=… %}`
(`survey/marker_icons.py`), in the browser `MarkerIcon.element(value, color, cssClass)`
(`survey/assets/js/marker_icon.js`), which is what `L.Icon.FontAwesome`, the crosshair overlay,
the draw button, star ratings and the editor picker all do. Unknown `set:name` → default pin.
The picker (`survey/assets/js/icon_picker.js`) reads `survey/assets/data/icon_catalog.json`,
generated by `scripts/build_icon_catalog.py` from Font Awesome Free 5.15.4 metadata plus Maki and
Temaki checkouts (not vendored — see the script docstring); the per-language search terms live in
`scripts/icon_terms/<lang>/*.json` and are merged at build time, so a "creators type X and find
nothing" report (PostHog `icon_search_miss`) is fixed by adding a row there and rebuilding. Keep the
Font Awesome CDN link in the three base templates on the version the catalog was built from.

**Display styles and the icon grid (change `choice-icon-grid`, #341)**: which `display_style`
values a type accepts is ONE table, `question_types.DISPLAY_STYLES_BY_TYPE` /
`allowed_display_styles()` — respondent rendering (`resolve_display_style`), `QuestionForm.clean()`,
both editor previews and ZIP import read it, and the modal's JS `DISPLAY_STYLE_TYPES` mirrors its
keys; a new style is one row there, never another hard-coded tuple. `icon_grid` (choice and
multichoice) renders `choice_icon_grid.html`: native radios/checkboxes wrapped in tile labels, so
value, required check and write-in are the list's. Per-option `icon`, `group` and `color` are optional keys
on the `choices` entries next to `other`, trimmed/capped by `question_types.normalise_choice_extras`
(`color` only as `#rrggbb`) on every save path and on import, and ignored by every other consumer. Tile icons go through
`{% marker_icon %}` and only when `marker_icons.is_drawable()` — no default pin on a tile. Icon
colour = the option's `color`, else `Question.color` unless it is the model default `#000000`
(= unset, CSS grey). The icon picker is ONE button (`js/icon_picker.js`, the input stays hidden as the value carrier) opening a fixed-position panel with Remove icon / No icon / "Use <typed value>"; never put a text field or browse button back next to it.
Single choice folds to the chosen row in `js/choice_icon_grid.js`; pop-ups that restore values with
`.prop()` must call `window.syncIconGrids(root)` (done in `initPopupFields`).

**Spray area (`spraycan`, change `spraycan-question-type`)**: the fourth geo type. The respondent
paints a cloud of dots with a brush (`js/spray_layer.js`, `L.SprayLayer`, one canvas per cloud,
one pre-rendered airbrush sprite stamped per dot — never a marker per dot, never a path per dot;
redraws only on `moveend`/`zoomend`); the answer is ONE `Answer` row per respondent with a `MultiPoint` in
`Answer.multipoint` (no cap by default; `validation_settings.max_dots` is the creator's optional one, `SPRAY_HARD_CEILING` only bounds scripted POSTs), normalised on save by `survey/spray.py`
(1 m grid, duplicates dropped — the count means painted area × dwell, not mouse events), brush
size in `Question.spray_brush`; `spray.describe()` is the "N dots · area" every surface shows. The column
is NOT named after the type, so the old convention `getattr(answer, input_type)` /
`f"{input_type}__isnull"` / `a.point or a.line or a.polygon` is gone: use
`question_types.geo_column()` and `Answer.geometry`, and take geo-type membership from
`question_types.GEO_TYPES` (every module's `GEO_INPUT_TYPES` is an alias of it). Two deliberate
exceptions: `MULTI_FEATURE_TYPES` (min/max features — a cloud is one feature) and
`SHARED_MAP_SOURCE_TYPES` (`layers.GEO_INPUT_TYPES` — a cloud never feeds a shared-map layer).
Responses (Map pane and Overview thumbnail) draws a spray question as one
`L.SprayAgreementLayer` — the public grid's look: share of respondents per geographic cell,
each counted once, NOT `leaflet.heat` (its zoom scaling flattens it); the public page gets a server-side grid of distinct-respondent counts per cell with cells below K
omitted (`survey/public_results_grid.py`), never the dots.

**Vendor facts on comparison pages (`survey/vendors.py`, change `market-guide-landscape-hub`, #259)**:
every claim the marketing site makes about another vendor is a `Fact(text, source, verified)` in
ONE registry — the public `https://` page it was read from and the ISO date — grouped into
`CATEGORIES` and `CRITERIA`. The market guide `/participatory-mapping-tools/` (the hub above the
`/alternatives/` pages; `/alternatives/` 301s to it) renders vendors × criteria from it, and the
three `/alternatives/` pages render criteria × (Mapsurvey, vendor) through
`partials/_vendor_vs_table.html`, so one correction reaches every page. **Never hand-write a
competitor cell in a template**; a fact the page does not state is `Fact("Not published", <page
read>, <date>)`. No price figure for any vendor but Mapsurvey (owner rule 2026-10-06): the model,
the trial and where a rate is listed; `test_no_competitor_price_figure_on_any_landing` scans
every `Fact.text` and the rendered hub. Import-time `_validate()` and `VendorRegistryTest` refuse
a fact without a source or with a bad date. The five category pages (#251/#252) still carry
hand-written tables; moving them onto the registry is the follow-up after #253. Mapsurvey's own
hosting fact is the United States (Render, Oregon) — the "EU-hosted / Frankfurt" wording that
survived on the Maptionnaire page until this change must not come back.

**API platform — the authorization layer (`api/`, change `auth-core`, #379; epic #378)**: every
programmatic client (personal token, OAuth grant, the REST API #380 and the MCP server #306 on
top) goes through ONE `api.auth.authenticate(request, audience)`. Bearer header only
— a session cookie never authenticates an API path, which is why those views are CSRF-exempt and
why `request.user` is never read there; use `request.principal`. Tokens are `oauth2_provider`
`AccessToken` rows (hashed at rest, looked up by checksum) with our `TokenProfile` beside them
(`kind`, `label`, `audiences` `api`/`mcp`, optional workspace binding, `revoked_at`); personal tokens
are `msk_…`, minted only by `api.tokens.mint_personal_token()` on `/editor/account/connections/`
(`/editor/account/mcp/` redirects there). Rights = scope ∩ organisation role ∩ survey role through
`api.rights` (`survey_for` answers 404, never 403; `section_for`/`question_for` always filter by the
survey — integer ids are IDORs otherwise). **Pro (`api` feature) is checked at the resource, per
request, on the organisation that owns the object** (`api.gates.require_pro_api(principal,
survey.organization)`), never at minting: a lapsed subscription stops access without revoking
anything. Limits are per token (`api.limits`: read/write minute windows, a daily cap, named caps via
`limits.hit(principal, "survey_create")`) plus a per-IP budget of failed bearers checked before the
lookup; `429` + `Retry-After`, fail-open on a cache outage. Errors are the envelope in
`api/errors.py` (`invalid_token`, `scope_missing`, `pro_required`, `not_found`, `rate_limited`,
`server_error`). A new endpoint is `@api_endpoint(audience, scopes=…)` + `rights` + `gates` and
calls the service layer — never a model directly (that is how an agent would skip
`coerce_creator_html`). Token values never reach logs: `_posthog_scrub_tags` keeps only path and
method under `API_PATH_PREFIXES`; audit and events carry ids. `OAUTH2_PROVIDER` pins RFC 9700 and
`api.tests.test_settings` runs the toolkit's deploy check. Contract for resource servers: `api/README.md`.

**REST API v1 (`api/v1/`, change `rest-api-v1`, #380)**: django-ninja at `/api/v1/`, OpenAPI at
`/api/v1/openapi.json` (public). Routes declare `auth=Bearer(<scope>)` (scopes checked before the
body is parsed), get the survey through `deps.survey(request, uuid, role=…)` (404 invisible, 403
`forbidden_role` under the role, `pro_required` on the owning workspace) and write ONLY through
`survey/services/` with `strict=True`; JSON is turned into the editor forms' dialect by
`forms_bridge.py`, which decides nothing. Input schemas are `extra='forbid'` (an unknown field is a
`422 validation` naming it). A structural change to a live survey is `409 draft_required` — the API
never creates unpublished changes unasked. Export is `export.export_response`, the same function
`download_data` returns; layer GeoJSON is `views.cached_geojson_response`. Ninja matches `{param}`
as a string, so a literal path segment (`/surveys/import`, `/sections/order`) is registered before
the parameterised route. The help centre's `reference/api.md` is GENERATED by
`scripts/build_api_reference.py`; `ApiReferenceFreshnessTest` fails when a route or schema changed
without regenerating it.

**MCP server (`mcp/`, change `mcp-server`, #306; epic item 4)**: the second resource server, served by
THIS process at `settings.MCP_RESOURCE_URL` = `<issuer>/mcp` (no trailing slash; `/mcp/` routes too
because `APPEND_SLASH` would 301 a POST). Streamable HTTP in **stateless mode**, hand-written in
`mcp/views.py` + `mcp/protocol.py` (no SDK: the official one is ASGI and streams): one POST → one
JSON response, `GET`/`DELETE` → 405, notifications → 202, NEVER an SSE stream (a worker held by a
stream is the 2026-09-18 outage). Versions `2025-03-26..2025-11-25`; a 2026-07-28 client's
`server/discover` gets `-32601` and falls back to `initialize`. Auth = `authenticate(request, 'mcp')`,
401 names `/.well-known/oauth-protected-resource/mcp` whose `resource` is the setting byte for byte.
`Mcp-Session-Id` is SIGNED (token id + nonce, `mcp/sessions.py`), nothing stored; another token's id
→ 404; a present `Origin` not the issuer's (or `MCP_ALLOWED_ORIGINS`) → 403. Tools live in
`mcp/tools/` as `@tool(...)` over `args_model(<v1 In schema>, survey=…, …_id=…)` — the REST schemas
plus ids, `$ref`s inlined — and call `api.v1.deps` / `forms_bridge` / `out` / the services with
`Actor(surface='mcp')`, never a model; `tools/list` omits tools the token's scopes lack and a call to
one is `scope_missing`. Protocol errors (unknown tool, schema failure) are JSON-RPC `-32602`; every
other refusal is an `isError` result carrying the REST envelope (two MCP-only codes:
`confirmation_required`, `has_responses`). `delete_survey`, `publish_survey`,
`publish_unpublished_changes` need `confirm: true`; `delete_survey` refuses a survey with answered
external sessions. Every result is `{"note": UNTRUSTED_NOTE, "data": …}`; descriptions are literals.
Limits: reads/writes share REST's windows by `read_only`, plus `limits.check_group('mcp.session')`
(300 / 10 min). Event `mcp_tool_called` (tool, outcome, token id; never arguments). The help page
`reference/mcp-tools.md` is GENERATED by `scripts/build_mcp_reference.py` (`test_reference` fails when
stale). Vocabulary: "unpublished changes", never "draft", in tool names and descriptions.

**The authorization server (change `oauth-server`, #313; epic item 2)**: django-oauth-toolkit's
views mounted by hand in `api/urls.py` — RFC 8414 document at the root, `/oauth/authorize|token|
revoke|register/`, nothing else (no introspection, device flow, OIDC, or protected-resource
document; that one is each resource server's). Issuer = `settings.OAUTH_ISSUER` (the preview's own
host under `IS_PULL_REQUEST`, else `SITE_URL` — `SITE_URL` is production on previews too). Clients
register themselves (open DCR behind a per-IP budget, CIMD through the toolkit's SSRF-hardened
fetcher) or are first-party rows in the admin. **Redirect URIs are ONE rule**, `api/oauth/redirects.py`:
exact match, `https` only, except loopback `http://127.0.0.1|[::1]|localhost` with any port (Claude
Code); the toolkit cannot express that, so `ALLOWED_REDIRECT_URI_SCHEMES` lists `http`,
`oauth2_provider.E003` is silenced, and the helper runs at DCR, CIMD, `Application` `pre_save`,
authorize and token time — never widen or bypass it. Every OAuth access token (`msa_…`; refresh
`msr_…`) gets a `TokenProfile(kind="oauth")` in `api/oauth/validator.py` with audiences from
`resource` (`api/oauth/audiences.py`, `API_RESOURCE_URLS`; none = both, unknown = `invalid_target`),
so rights, the Pro gate and limits apply unchanged; `code_checksum` is how a code redeemed twice
revokes its whole family. Consent (`api/authorize.html`) shows the redirect host ABOVE the
attacker-chosen name, publish/delete as switches off by default, issued scope ⊆ requested (signed
hidden field), and is remembered while an unrevoked refresh token covers the request. `/oauth/*`
responses get DENY / `frame-ancestors 'none'` / no-store from `api.middleware`. Connected apps and
*Disconnect* live on `/editor/account/connections/` (`api/oauth/grants.py`). Ops after a deploy:
`scripts/oauth_reachability_check.py` and a bot-shaped curl of `/api/v1/me` — the Cloudflare in
front of production is Render's edge, not a zone we manage, so there is no rule of ours to set.

**Service layer (`survey/services/`, change `rest-api-v1`, #380)**: the ONE write path for surveys,
sections, questions (choices, validation settings, visibility rules, translations, order) and the
lifecycle (transition, unpublished changes create/publish/discard, restore version). The editor views
and the REST API both call it; neither writes those models directly. A service takes an
`Actor(user, ip, surface)` and plain values, never a `request` (`audit.record(actor, …)` is the
request-free audit writer; `audit(request, …)` delegates to it). Input is validated by binding the
SAME editor form (`SurveyHeaderForm`, `SurveySectionForm`, `QuestionForm`) to a dict — that is what
keeps `coerce_creator_html`, `clean_redirect_url` and every `clean()` rule identical across surfaces
— and `partial=True` gives PATCH semantics on top of forms written for full posts. Everything is
validated before anything is written, inside one transaction (a layer created from
`layer=answers:<code>` goes with a refused save). Refusals are `services.errors` types
(`ValidationFailed` with `fields` and, for questions, a `stage`; `StructureLocked` with `reasons` and
the draft; `ContentLocked`, `AnswersAtRisk`, `TranslationGaps`, …) that each surface maps to its own
response — the editor to exactly what it always returned. Questions speak the editor's dialect
(`QuestionForm` fields + `choices_json`, `vs_*`, `sm_*`). Strict visibility checking
(`visibility.validate_rule`) is opt-in (`strict=True`, the API); the editor keeps fail-open.
Groups, duplicate, paste and move still live in their views. A test that patches a function the
editor used to call directly patches it where the service imports it (`survey.services.locks.screen_survey`).

**Billing — Pro on PayPro Global (`billing/`, change `paywall-payproglobal`, #268)**: PayPro is the
Merchant of Record; we own the checkout link out (`billing/checkout.py`, the ONLY place a PayPro URL
is built, with `x-org_id/x-user_id/x-plan/x-nonce` and `ipn-domain`), the webhook in
(`POST /billing/ipn/` → `billing/ipn.py`: verify source IP + SHA256 `SIGNATURE` + MD5 `HASH` over the
RAW strings, store once in `BillingEvent`, apply the state machine to `Subscription`) and the
entitlement (`billing.entitlements.for_organization(org)` — Pro while `now < current_period_end` in
active/past_due/suspended/terminated, never after refund/chargeback/finish). **One grant path**: only
the webhook view writes `Subscription.status`/`current_period_end`; the return page polls, the
billing-page API actions (`billing/ppg.py`, shown only when `PPG_API_SECRET_KEY` is set) ask PayPro
and wait for the webhook. Features are the registry in `billing/features.py` (`unbranded`,
`pro_help`); gate with `require_feature` / `{% has_feature org "key" as x %}`, never a column.
`survey/ai/quota.py::check_quota` reads the same entitlement. `PPG_PRODUCTS` empty = nothing sold
(rollback). Test-mode webhooks are applied only where `PPG_ACCEPT_TEST_IPN` is true (previews). The
badge partial and `public_results.html` honour `show_branding` only under `unbranded`; the settings
form disables the switch otherwise. Setup checklist, env vars and the PayPro email:
`billing/README.md`. Reference digest of PayPro's docs lives outside the repo (local skill
`payproglobal`). Tests: `./run_tests.sh billing` — one module per capability, `billing/tests/test_<capability>.py` ↔
the spec of the same name (the rule proposed for `survey` in #273); payload and subscription
builders in `billing/tests/helpers.py`.

**Pro trial (change `pro-trial-allowances`, #471)**: the SECOND entitlement source, next to
`Subscription` — `EntitlementGrant` (`kind='trial'`; #322's academic grant is the next kind) with one
`GrantAllowance(feature, limit, used)` per feature. Not days of Pro but counted uses for
`TRIAL_DAYS` (90) after the OWNER's click (`POST /org/<slug>/billing/trial/`, `billing/trial.py::claim`):
`api` 500, `unbranded` 1, `pro_help` 1 (`TRIAL_ALLOWANCES` in `billing/features.py`; empty = not
offered, the rollback). One trial per person (partial unique on `claimed_by`) and per workspace; never
automatic, never on Pro; AI generation is not in it (free on every plan). The webhook still owns
`Subscription`; a grant is a different row with a different writer. **Three questions on
`Entitlements`**: `has(key)` = the PLAN includes it (plan cards, `is_pro`, lapse task); `may(key)` = a
NEW use is allowed (plan, or a live trial's remainder) — every gate that decides an action
(`require_feature`, `require_pro_api`, `pro_organizations`, `SurveyHeaderForm.unbranded`);
`covers(key)` = in force (plan, or a live trial includes it, spent or not) — what `{% has_feature %}`
answers, because a survey unbranded under the trial stays unbranded after its one switch-off is
spent. A use the plan does not cover is counted ONLY by `trial.consume()` — one `UPDATE … WHERE used
< "limit" RETURNING`, race-safe — at the point of use: `require_pro_api` (once per request per
workspace; `mcp.protocol.call_tool` resets the memo per tool call), `services.surveys.update_settings`
(a badge switch-off, inside the service transaction), `org_help` (a stored request). Expiry is a
comparison, no cron, no mail. The viewer's state (`available | live | exhausted | expired |
used_elsewhere`) is `trial.state_for(org, user)`, rendered by `billing/_trial_offer.html`;
`pro_required` carries `trial: none|exhausted|expired`. Staff end a grant by setting `revoked_at` in
the admin; the counters are read-only there.

**Support chat (Chatwoot, change `chatwoot-support-chat`, #291)**: one partial,
`partials/_support_chat.html`, included by the three base templates; config and the signed-in
creator's identity come from `survey.context_processors.support_chat`. The identifier is
`str(user.pk)`, signed with `identifier_hash = HMAC-SHA256(CHATWOOT_HMAC_TOKEN, pk)` on the
server — the token never reaches the browser; empty `CHATWOOT_WEBSITE_TOKEN` = no widget, no
third-party request (tests, local dev, previews without the env group). On working surfaces
(`hide_bubble`, i.e. `MOBILE_EDITOR_NAV`) the widget never speaks first: no bubble, no unread
pop-up; the entry point is the "?" menu in the header (`editor/partials/_help_menu.html`) and
"Help & support" in the ⋯/account menus, and an agent reply lights the `.support-unread` dot on
them. `openSupportChat(event, context)` opens the chat and sends `context` to the agent as
contact custom attributes (workspace, plan, page, survey are sent on every page) — the hook for
help at the point of failure (#295). Chatwoot's own cookies outlive our session, so a page
rendered for a different visitor clears them before the SDK loads; do not use
`$chatwoot.reset()` for that (it reloads the frame without a second `chatwoot:ready`).

**Help centre (`help/`, change `help-site`, #298)**: help.mapsurvey.org is a Starlight (Astro) site
built from `help/` by its own Render static service (`mapsurvey-help`, `buildFilter: help/**`,
automatic PR previews because static sites are free; previews mark every page `noindex`). Sections
follow Diátaxis — `start-here/` (tutorial), `how-to/`, `reference/`, `troubleshooting/`, `learn/`
(citizen engagement as a practice, written from `docs/research/survey-design-rules.md`),
`use-cases/`, `faq.md` — and `help/CONTRIBUTING.md` holds the page shapes and the FAQ rule (a
question is added only when someone asked it; source in a comment). A feature's guide ships in the
feature's PR. **Product → help links go through `survey/help_links.py`** (`HELP_URL.<key>` from the
`help_site` context processor; `HELP_SITE_URL` empty = no links) and `HelpSiteLinksTest` fails when a
registry path has no page under `help/src/content/docs/`, so a renamed page needs a `redirects` entry in
`help/astro.config.mjs` and a registry update in the same commit. The "?" menu's "Help centre" item
and the "Learn more" links (reference layers, embed, export, Pro) are the only entry points; the
help site's "Still stuck?" link is `mapsurvey.org/?support=1`, which opens the chat for a signed-in
creator (`open_on_load` in the support_chat context). `npm run build` in `help/` fails on a broken
internal link (`starlight-links-validator`); the MCP pages are `draft: true` until mcp.mapsurvey.org
is live.

**Translation table (change `translation-table`, #454; epic #393)**: the **Translations** tab
(`survey/translation_views.py`, `editor/survey_translations.html`, `js/translation_table.js`) is
where translations are written from the UI; the Translations blocks of the section, question and
group modals, the per-language columns of the choices table and the non-primary tabs of the thanks
panel are READ-ONLY mirrors that link to the row (`?to=<lang>#row-<key>`), and the editor views
pass `translations=UNSET` to the services (the API and MCP still write through them). One module,
`survey/translation_table.py`: an **occurrence** is one translatable field addressed by CODES, never
ids — `section:<code>[#n]:title|subheading|next_label`, `question:<code>:name|subtext`,
`question:<code>:choice:<code>`, `group:<code>:title|description`, `survey:thanks` — so nothing has
to be copied on the draft copy, publish or restore; `occurrences()` walks the survey in respondent
order, `rows_for()` groups identical normalised source text (`t:<hash12>` keys; a group whose
occurrences carry different translations renders split), and **`apply()` is the one writer** (the
page, the CSV import and the future AI job) — it routes every value to the entity's service path
(`save_translations`, `set_choice_names`, `set_thanks`), so caps, `coerce_creator_html`, the content
lock and the re-screen are the modals'. **Outdated** = `TranslationSource` (keyed by the canonical
survey + occurrence key + language) holds the hash of the primary text a translation was written
against; every translation write records it for the fields whose value changed (`record_all` from
the table), a base-text save never touches it, and a translation with no row reads as translated.
`translation_gaps.survey_translation_gaps` stays the one gap engine — it now counts the Next label,
the thank-you page and stale rows (`"<lang> (outdated)"`) — so badges, the publish warning, the API
409 and the table cannot disagree. CSV: `export_csv`/`parse_csv`/`values_from_csv` — the customer's
Page/Element/source/translation layout plus `key` and `status`, matched by key then by source text,
formula cells apostrophe-guarded, rich text as plain paragraphs. Languages are added from the tab
through `services.surveys.update_settings` (owner only); the pair is `?from=&to=` and remembered in
`localStorage['msTranslations:<uuid>']`. Build takes `?question=<id>&lang=` / `?group=<id>` to open
that modal at its Translations block.

**Section layout controls (change `section-layout-controls`, #473)**: three independent per-section
settings — the stage `SurveySection.layout` (`map | image | form`; `image` shows `stage_image`, else
the survey's `cover_image`, else a tinted area), `panel_side` (`left | right`) and `panel_width`
(`default` = 420 px, `third`, `half`). Map-less stages are ONE constant, `models.MAPLESS_LAYOUTS`
(`section.has_map`): the section form, the question form's type filter and `layers.py` read it, so
`image` excludes geo questions exactly as `form` does — never test `layout == 'form'` again. Rendering
is body classes (`SurveySection.layout_classes()` on a direct load, `initSection()` step 0 on an HTMX
swap from `#section-data[data-panel-side|data-panel-width|data-stage-image]`) plus one CSS variable
`--panel-w`; the defaults set no class, so an untouched survey renders as before. Side and width rules
live ONLY inside `@media (min-width: 769px)` in `main.css` — on a phone the panel stays the 88 % overlay
and an `image` section is a picture band over one scrolling column. The picture is shared within a
survey family and copied across surveys (`copy_section`, like `Question.image`), rides the ZIP as
`images/sections/<section pk>_<name>`, is read-only in the API (`stage_image` URL) and deleted on purge.

**Hierarchical Questions/Answers**: Both Question and Answer models support self-referential parent relationships via `parent_question_id` and `parent_answer_id` for conditional sub-questions.

**Conditional visibility (`CONDITIONAL_VISIBILITY` kill switch, default ON)**: a
`visibility_rule` JSONField on `Question` and `SurveySection` (`{"question_code", "choice_codes"}`,
any-of match on an earlier `choice`/`multichoice` answer) drives who sees what. One engine —
`survey/visibility.py` — feeds the respondent form, POST discard/purge, section navigation,
progress, and the editor badges/lint, so runtime and editor can never disagree. Hidden ⇒ never
required, submitted answers discarded, abandoned branches purged server-side. Broken rules fail
OPEN (shown to everyone) and are badged in the editor. Rules ride ZIP export/import
(`_apply_visibility_rules` drops unresolvable ones with a report line) and duplication
(`cloning.py` remaps intra-section controllers; cross-survey paste drops the rule). Do NOT reuse
`parent_question_id` for visibility — that relation means "geo popup sub-question". Env var off ⇒
rules stored but inert, editor hides the Visibility block.

**Question groups (`QuestionGroup`, change `question-groups`, #340)**: a container, not a question
type — a title, a rich-text description (`coerce_creator_html` on every write), a display style
(`plain | card | collapsible`) and one `visibility_rule` for a run of questions in a section or in a
geo / Objects pop-up (`parent_question`). Answers stay rows on the questions; export, Responses and
public results do not know groups exist. **One continuous order**: a group's `order_number` is a
slot in the same sequence as its sibling questions and its members (`Question.group`, `SET_NULL`)
follow it contiguously, so `section.questions()`/`subQuestions()` and the visibility engine's
"controller is earlier" test are unchanged; anything that computes a new `order_number` must count
groups (`survey/groups.py`: `max_order`, `next_order`, `shift_down`), and anything that DRAWS
questions goes through `group_runs` (respondent: `SurveySectionAnswerForm.field_runs` →
`partials/question_fields.html` → `partials/question_group.html`; editor: the `editor_runs` tag →
`group_list_item.html`). Visibility treats a group as host kind `'group'` judged at its own
order; a member is visible only if its group is (`VisibilityMap.group_visible`, `question_own` for
the respondent page); client rule maps key groups `group:<code>`, always before their members.
Editor endpoints live in `survey/editor_group_views.py`; the one reorder endpoint for nested lists
is `editor_items_reorder` (ownership-checked, renumbers 0..N, sets membership); a group change
re-renders the section panel rather than patching rows. Deleting asks: only the group (members
stay in place) or with its questions (the usual 409 answer-loss acknowledgement). Groups ride the
ZIP (`groups`, `sub_question_groups`, `group`), every copy (`cloning.clone_groups`,
`clone_top_level_questions`), comments (`group:<code>` anchor) and content screening. AI
generation writes no groups.

**Pop-up rules (change `subquestion-visibility-rules`, #338)**: a sub-question of a geo /
`layer_objects` question may carry the same `visibility_rule`, but its controller is an EARLIER
`choice`/`multichoice` sub-question of the SAME pop-up (`parent_question_id`), never a section
question. Those rules never enter `compute_visibility` (a pop-up is answered once per feature):
`visibility.popup_visibility(parent, answers_by_code)` judges them per feature/object, and the
section POST calls it for every geo feature (from its properties) and every object
(`_save_object_answers`), storing nothing for a hidden follow-up. The respondent pop-up keeps every
sub-question in its HTML; `conditional_visibility.js` toggles them per pop-up `<form>` from
`#section-data[data-popup-visibility-rules]` (bound in `initPopupFields`, i.e. after a feature's
values are restored), and the geo shell prunes hidden cards' properties on Apply/close. Editor:
`_visibility_block_context(..., 'subquestion', host, parent)` renders the block with one group
("This pop-up"); `visibility_info` resolves the kind from `parent_question_id_id`, so the recursive
`question_list_item.html` badges sub-question rows unchanged. Import resolves a sub-question rule
among the imported siblings; `clone_question` remaps it to the cloned sibling on every path,
including cross-survey paste (the controller travels with the parent).

**Shared map (`question`-sourced reference layers)**: a `SurveyMapLayer` with
`source='question'` holds no creator objects — its `LayerObject`s are MATERIALISED from
respondents' answers to the geo question named by `source_question_code` (a code, not a FK:
layers belong to the canonical survey, question rows are copied per version). Materialisation
runs at the end of the section POST (`layers.sync_question_layers_for_session`) and keys
objects `s<session>-<n>`, never by answer id, because the POST deletes and re-inserts a
session's answers on every submit and a re-keyed object would lose the reactions other
respondents left on it. Respondents get `build_question_layer_geojson` per request
(`no-store`, own marks omitted, only `status='visible'` from clean sessions); creator
surfaces read the cached `layer.geojson` (every status, clean sessions) rebuilt on
materialisation, moderation and session-status changes. Reactions are ordinary answers to
the sub-questions of an "Objects on the map" question bound to that layer; `show_tallies`,
`show_comments`, `approve_first` on the layer decide what other respondents see, and
`LayerObject.status` / `Answer.hidden` are the creator's per-item moderation. The object
editor is read-only for such layers; deleting the source geo question is refused.

**Coverage surface (change `responses-coverage-surface`, issue #242, epic #245)**: on the Responses
Map pane a LineString/Polygon answer layer's menu offers *Create Coverage*, a `coverage` slot of
the `LayerManager` that draws, per world-anchored metre cell, the share of respondents whose shape
covers it (polygons: inside, holes excluded; lines: within `corridorMeters`, default 20 m). It is
`L.SprayAgreementLayer` (`js/spray_layer.js`) fed `{id, geometry}` members instead of `{id, dots}`
clouds — ONE binning seam (`_bin` → `_rasterise`, an offscreen canvas at cell resolution clipped
to the viewport, even-odd fill, stroke width = corridor in cells, alpha read-back) for spray,
polygons and lines, so the three never disagree; do not add a second density renderer. Each
respondent counts once per cell; the row reads "≤ N of M respondents". Derived in the browser
only — exact counts for export and public results are #243, the agreement contour #244.

**Reference layer style**: `SurveyMapLayer.style` (JSON) holds the base look beyond `color`
(opacity, weight, fill_opacity, radius, icon) and at most one rule `by` one object property
(categories or graduated classes, plus `other`). `layers.normalize_style` is the ONE validator
— the update endpoint and the ZIP cleaner both run it, so a style that saves is a style that
draws; never read `layer.style` raw. `ref_layer_factory.html`'s `styleFor()` is the ONE
renderer (rule class → simplestyle in the file → base) for the respondent map and the
Responses map alike; `layers.match_class` mirrors its matching for the server-side legend
(`legend_for`, delivered as metadata). The object editor draws with its own code and does
not honour rules yet.

**In-app changelog (change `in-app-changelog`, issue #227)**: "What's new" entries are files in
`survey/changelog/<YYYY-MM-DD>-<slug>.html` — a `---` header (`title`, `kind: new|fixed`,
optional `link` URL name, optional `image` static path) followed by an HTML body, English only,
shipped in the PR of the change they describe (format in `survey/changelog/README.md`; the loader
is `survey/changelog.py`, read once per process). Seen-state is ONE watermark per creator,
`CreatorPreferences.changelog_seen` = the newest id seen; ids start with the date, so "unseen" is a
string comparison. The card (`editor/partials/_whats_new_card.html`, included from
`editor_base.html` AND `base.html`, never from `base_survey_template.html`; the `whats_new`
context processor also returns nothing under `/surveys/` and `/r/`) shows only the latest unseen
entry, once; "Got it" / × / the page / "Don't show these" all move the watermark.
`changelog_cards` off hides the card only — the page `/editor/whats-new/`, the gift icon and the
account-menu item stay. New accounts start seen (`seed_changelog_watermark` in `signals.py`).
`ChangelogEntriesTest.test_shipped_entries_load` parses every file, so a malformed entry fails CI,
not every editor page. The first entry (`2026-10-02-whats-new.html`) announces the cards themselves; #226 (empty sessions hidden by default) writes the next.
**Hero tier (change `changelog-hero`, #423)**: an entry with `tier: hero` (+ `art`/`image`,
`link`+`link_query`, `cta_label`, optional `help`, `chips` with `{survey}`, `show_if`/`note_if`
from the predicate registry `survey/changelog_audience.py`) renders as a full-width banner on the
dashboard (`editor/partials/_whats_new_hero.html`, included from `editor.html` ONLY) instead of
the corner card. A hero is *pending* while unseen, ≤30 days old and in audience; while pending no
corner card renders anywhere (`whats_new.card` is None), a hero never becomes a corner card, and
closing it marks everything seen. Both partials remember the closed id in
`localStorage['msWhatsNewClosed']`, so a close whose POST failed stays closed — the second
"close, close, close" click was the owner's reason for the rule. Budget: two heroes ≥14 days
apart (`test_hero_budget`). Events carry `tier`; `changelog_card_clicked` (`target=cta|help`)
is the interest signal per feature.

**Comment threads (`CommentThread`/`Comment`/`CommentAttachment`, spec `survey-comment-threads`)**:
workspace members discuss a survey where it lives — the survey as a whole, a question, a section, a respondent
session or a public-results block — in ONE slide-in drawer (`editor/partials/_comments_drawer.html`, included
once from `editor_base.html`; `js/comments_drawer.js` + `css/comments.css`). Row badges
(`section_list_item`, `question_list_item`, `pr_block_list_item`) and the toolbar/modal buttons
call `CommentsDrawer.open({anchor: "<kind>:<page id>"})`; the panel is an HTMX partial from
`survey/comment_views.py`. **Anchoring rule**: `thread.survey` is always `canonical_of()`, question
and section anchors are `code`s (never FKs — `publish_draft()` replaces the rows), session and
block anchors are FKs; a `CheckConstraint` enforces exactly one anchor. All of that lives in
`survey/comments.py` (`resolve_anchor`, `anchor_fields`, `open_counts`, `participants_of`, writes);
views only check roles. Every role opens/replies/resolves; delete = author or owner. Bodies are
PLAIN TEXT escaped on render — `coerce_creator_html` does not apply. Attachments sit on the private
media tier under random keys and are served only by `attachment_download`. Badge counts come from
one grouped query per page (`thread_counts` in every row-rendering context; the `thread_count`
filter) and are refreshed client-side on `HX-Trigger: threadCountsChanged`, so a render site that
forgets the context under-counts until the next action, never errors. Notification mail goes to the
thread's participants (creator, authors, everyone mentioned), never the actor, one Celery task per
recipient (`survey/tasks.py`) through `survey/mail.py::send_templated_mail` and `SITE_URL`
(defaults to `NEWSLETTER_SITE_URL`); the same helper is where invitation/activation mail should move.
Deep link: `<editor page>?section|block|session=<id>#thread-<id>`. "New since you last looked" is
`CommentSeen` (one row per member+survey, bumped when the drawer renders): `open_counts(survey,
user)` also returns `new_keys`/`new_total`, which drive the red dot on badges, the toolbar count and
the "N new" pill — so every render site passes `request.user`. Authors edit their own comments in
place (`edited_at`, no re-notification). Response anchors are labelled with the Responses ordinal
(`comments.session_seq`), never the session id.

**Editing a live survey (`LIVE_SURVEY_EDITING` kill switch, default ON; change `edit-live-survey`)**:
a published/closed survey takes SAFE edits in place (wording, help text, translations, added options,
map/display settings) with no draft and no new version; STRUCTURAL edits (add/delete/reorder/paste,
type, layer binding, visibility rules, section code, removing an ANSWERED option) go to the draft
copy, which every creator surface calls **"Unpublished changes"** (Publish changes / Discard changes;
"version" only on Responses and exports). One rule set in `versioning.py` (`is_live`,
`structural_question_changes`, `structural_section_changes`, `removed_answered_choices`, shared with
`check_draft_compatibility`). Views: `_edit_locks(survey)` → `(is_read_only, structure_locked)`;
content endpoints call `_check_content_edit_allowed`, structural ones keep
`_check_structural_edit_allowed` (403). Templates gate structural controls on `structure_locked`
with `data-gate="<action>"` (opens the gate modal in `survey_detail.html`, which posts `then` +
`section_code` to `editor_create_draft`, `editor` role and up — owners alone publish/discard),
content controls on `is_read_only`. A new editor
control must pick one of the two — never `survey.status`. The draft copy and the editor's
duplicate/paste take every plain `SurveySection`/`Question`/translation field from the model's
field list (`cloning.plain_field_values`, `copy_section`); a field that must NOT travel is an
explicit exclusion there, never an omission — #329 was a hand-written list in `versioning.py` that
silently dropped `visibility_rule`, `layout`, `next_label` and `hidden_layers` on every publish.
`DraftCopyKeepsFieldsTest` compares every concrete field between live and draft, and
`report_draft_field_loss` (read-only) lists surveys whose publish already lost them. While a draft exists, Build redirects to
it (`?live=1` shows the live survey read-only) and live content edits are refused, because
publishing the draft replaces the live structure. Both confirmations (the gate and "Publish
changes") carry "Don't ask again": ONE browser-side preference, `localStorage['msEditorConfirmations']`
(`window.EditorConfirm` in `editor_base.html`), restored from the account menu; the compatibility
dialog is never skipped. Switch off ⇒ the old read-only page and "draft" vocabulary.

**After the last page (`SurveyHeader.redirect_url`, change `fix-redirect-url-validation`, #271)**: the
value is `"#"` (built-in thanks page) or an absolute http(s) URL, nothing else. Never read it raw:
respondent redirects go through `survey/redirects.py::completion_url(survey)`, imports through
`clean_redirect_url`. It used to be free text, and hashtags, thank-you messages and `#https://…`
(typed after the pre-filled `#`) kept respondents pressing Finish on the last page. Settings shows it
as the "After the last page" choice; the form refuses anything that is not a full http(s) address.

**Ways to start (change `first-survey-onboarding`)**: a workspace with no surveys and, by default,
"+ New Survey" lead to the START PAGE `/editor/surveys/start/` (`editor_survey_start`) — three cards,
*Start from scratch* / *Draft with AI* / *Connect your AI agent* — not to the create page.
**One click on a card does its action** (change `start-cards-one-click`, #335): the blank card IS
the submit `<button>` of its form, the AI card IS a link to `?from=start`, comes FIRST and is
called the *Survey wizard* with a "Best to start" badge (AI drafts publish ~2.5x as often; the
AI path is the **Wizard** on EVERY creator surface — start card, brief panel, intercept, feedback
strip, generation errors, help — and the only sentence that says what it is ("The Wizard is an AI
agent: …") is the provider disclosure on the create page; labels via `_survey_start_labels()`, the
model's choice label is unchanged; marketing landings still say AI); there is no selection
step, no detail block and no "Always start this way" on the page — creators clicked the card over
and over when a click only selected it. Do not bring a "choose, then confirm" step back.
`CreatorPreferences.survey_start_default` (`''` ask / `blank` / `ai`) is set ONLY on the personal
**Preferences** page `/editor/account/` (`editor_account_preferences`, login only, no org role;
"Preferences" in the account menus of BOTH bases) and is
what the dashboard renders the button from (context processor `survey_start`): `blank` makes it a
POST form to `editor_survey_create_blank`, the one-request empty survey ("Untitled survey", the
creator's UI language, map from the chain below) that shares `_finish_blank_survey` with the create
page's manual action so the two cannot drift. POST, never GET. The create page keeps every old
link; `?from=start` only swaps "Skip and start from scratch" for a way back. **Where a new map
opens is ONE chain**, `survey/map_start.py::suggest_start_position` — `browser` (coordinates the
creator's browser gave: permission already granted, or asked on the click that submits; NEVER on
page load) → `org_survey` (newest positioned survey in the workspace) → `country` (`CF-IPCountry`
from Render's Cloudflare edge, trusted only under `CLOUDFLARE_TRUSTED`; else the `Accept-Language`
region, never `en-US` — the stock-browser default says nothing; `survey/country_centroids.py`) → `world`. The create page's first `setView` and the AI
draft (through the same hidden fields) start there — the Berlin default is gone and must not come
back. `survey_created` carries `surface` (`start_blank` | `create_page`) and `map_source` (the
rung, `creator` when the map was framed, `brief` when the AI task geocoded the brief): names only,
never coordinates. `/editor/account/mcp/` (`editor_account_mcp`) is a redirect to
`/editor/account/connections/` (change `auth-core`), where the MCP block with "Tell me when it's
ready" (`agent_access_requested_at`, the launch list, one event) sits under the tokens until #306
ships — the URL name, the account-menu item "API & connections" in BOTH bases and the "?"-menu
item stay. New creator strings go into all offered catalogs (`TranslationCatalogHygieneTest`
enforces it); the entries are appended by hand like PR #274, not by `makemessages`.

**Session Management**: Survey sessions are created on first section view and tracked via `request.session['survey_session_id']`.

**Empty sessions (change `hide-empty-sessions`, issue #226)**: a session with no top-level `Answer`
(`parent_answer_id IS NULL`) is EMPTY — someone opened the survey and left (71% of external
sessions in Sept 2026). One definition, `analytics.nonempty_sessions(qs)` / `empty_sessions(qs)`;
`compute_session_issues`, the v2 Responses page and `export.excluded_sessions` all go through it.
The v2 page hides empties unless the `rv2_show_empty` cookie is `1` (`analytics_views._show_empty`;
the legacy page and every other `SurveyAnalyticsService` caller keep `include_empty=True` and see
all sessions). `service.empty_count` feeds the "N opened without answering" line
(`editor/partials/_empty_sessions_toggle.html`). Response numbers `#N` come from
`service.sequence_numbers()` — rank among non-empty sessions; empty rows carry none — and
`comments.session_seq` follows the same rule. "Empty" is not an Issues-menu entry on v2. Exports
never contain empty sessions, whatever `include_all` says. The funnel/Perf pane (`SurveyEvent`) and
the public results `response_count` still count every session. The section POST treats
whitespace-only values as blank and stores text/number values stripped.

**Data export (`survey/export.py`, spec `responses-export-formats`)**: `download_data` is a thin
view; the work is one collector and several writers. `collect()` walks the database ONCE into an
`ExportBundle` (per geo question a FeatureCollection plus the GEOS geometry and session of every
feature; per-session rows; object-answer records; file answers), and every format is a writer over
that bundle, so the flat table, the workbook and the GIS files can never disagree with the GeoJSON.
URL contract: `?format=zip|xlsx|csv|gpkg|shp|kml` (no `format` = the legacy GeoJSON+CSV archive,
byte-for-byte, for old links and scripts), `version`, `include_all=1`, `completed_only=1` (the
Responses overview's definition through `analytics.completed_session_filter`, never a second one),
`files=1` (uploads; turns a single-file format into a ZIP). The **observations** table is one row
per placed feature with `lat`/`lon` (centroid for lines/polygons), `wkt`, and sub-question columns
merged BY NAME across questions (`question` disambiguates) — the shape a clerk without a GIS asked
for. Excel is written in `openpyxl` write-only mode to a temp file and streamed with `FileResponse`;
GeoPackage/Shapefile/KML come from ONE `ogr2ogr` call over an OGR VRT listing every layer
(`gdal-bin` is in the image for GeoDjango; `OGR_AVAILABLE` hides those formats on a host without it).
The dialog is `editor/partials/_export_modal.html` + `js/export_dialog.js`, included once per page
and fed by the opener button's `data-*` (survey, version list, has-files); it builds a GET URL, so an
export is always a copyable link. Naming: the data download is "Export data" everywhere, the
survey.json backup group is "Backup (survey file)" — creators confused the two.

**ZIP import is a job (`SurveyImportJob`, `survey/tasks.py::run_survey_import`)**: the
`import_survey` view stores the archive on the private media tier under a random
`import_jobs/<uuid>.zip` key, enqueues the task and redirects; the Celery worker calls
`import_survey_from_zip` (same function the CLI uses), records the outcome (survey, warnings
or the validation error) on the job row and deletes the archive. The dashboard renders
`editor/partials/import_jobs.html` for the creator's open jobs and those finished in the last
24 h, polling every 3 s while one is open; finished cards are dismissed (deleted) by the
creator. Tests wrap web-import POSTs in `_eager_import()`, which turns `.delay` into the task
itself — the suite has no broker. The task runs once per job: a redelivered message finds the
row past `queued` and returns.

**Public results page**: Creators expose aggregated results at `/r/<slug>/` via `PublicResultsPage` (1:1 with `SurveyHeader`) + ordered `PublicResultsBlock`s. Config tab at `/editor/surveys/<uuid>/public-results/`. Rendering logic in `survey/public_results.py` (`PublicResultsService`, `render_page_data`, `freeze_page`/`unfreeze_page`); editor views in `survey/public_results_editor.py`. Aggregates run over CLEAN sessions only (not deleted, excludes `not_approved`/`on_hold`) across the canonical survey + all versions. Privacy: k-anonymity masks buckets `<K` (default 3); geo popups expose only creator-selected `geo_label_fields`; individual free-text answers are never published. Hybrid `live` (60s cache) vs `frozen` (snapshot) mode. Visibility `public` (indexed, in sitemap) vs `unlisted` (noindex). The page config is intentionally NOT included in survey ZIP export/import.

**Category landings (`/community-engagement-platform/`, `/civic-engagement/`,
`/public-consultation-software/`, `/participatory-budgeting/`; change `seo-landings-rewrite`, #251)**:
one section order on all four (hero → definition → four screenshot steps → feature grid → comparison
table vs two incumbents + "when they fit better" → use cases → pricing → siblings → From the field →
FAQ), styled from the "Category landings" block of `landing.css`, not per-template `<style>`. The Pro
price ($49 a month / $490 a year per workspace) lives in `partials/_landing_pricing.html` and
NOWHERE else on the site, including meta descriptions (`SeoCategoryLandingContractTest` fails if a
template names it): taking the price off the site is one edit. `partials/_landing_siblings.html`
links the four pages to each other (`current`, `audience`). Every comparison cell comes from the
vendor's published pages, dated in the note under the table; "not published" is a valid cell, and
the tables follow the vendors' pages over our older dossiers (Go Vocal draws lines and polygons and
has an AGPL Free Edition; Social Pinpoint's Social Map exports GeoJSON). No marketing page may claim
EU hosting: the hosted service is in the United States, self-hosting is the EU-residency answer.
Rewriting a landing means bumping its `lastmod` in `seo_landings.py` and rewriting its FAQ for the
variant queries Search Console shows it for (`googlesearchconsole_search_analytics_by_query_page`
in PostHog).

**Customer stories (`Story`, `StoryImage`; change `customer-stories-showcase`)**: the homepage
"From the field" carousel and `/stories/<slug>/` are DB rows, but the REPO is the source:
`survey/story_data/<slug>/` holds `story.json` (fields, cover/card/logo file names, `images`
key→file), `body.html` and `images/`; `python manage.py seed_story <slug> [--draft]` installs or
refreshes the row (idempotent by slug, keeps id and first `published_date`, uploads pictures to
the public media tier). Body pictures are `{img:<key>}` tokens resolved by
`survey/stories.py::render_body` against the story's `StoryImage`s, so one body works on
production, previews and laptops whose media prefixes differ. The body is staff-authored HTML
rendered `|safe` — not creator input. A re-run of the command overwrites admin text edits.
**Publishing is a separate step (change `story-draft-publishing`)**: `seed_story <slug>` installs
a NEW story as a draft and a re-run keeps the current state (`--publish` / `--draft` force it), so
prepared stories can sit on production unpublished. The repo is public: a story whose customer
has not approved it yet is NOT committed; copy its directory to the server and run
`seed_story <slug> --from <dir>`. Staff open a draft at its normal URL (draft
banner, `noindex`); everyone else gets 404, and drafts stay off the landing, `/stories/` and the
sitemap. The customer's written OK on text and pictures (each `story_data` dir carries a
`CREDITS.md`) → the admin's "Publish" action or the list checkbox. A story body may carry the
**Lessons learned** callout (`<aside class="sd-lessons">`, change `story-lessons-learned`): one
look in every story, each lesson with an "In Mapsurvey" line tagged Available / Built for … /
Not yet; `Story.has_lessons` puts a badge on the card. The whole path from consent to `seed_story` — prod-DB facts, heat maps and phone
screenshots taken on a LOCAL import of the survey (opening the live one creates an `external`
session in the customer's data), the approval HTML (`scripts/story_approval_html.py`) and cover
letter — is the `customer-story` skill (`.claude/skills/customer-story/SKILL.md`);
`StoryDataDirectoriesTest` seeds every `story_data` dir.

**Story topics (change `story-topics`, issue #250)**: `Story.topics` is a list of slugs from the
ONE registry `survey/topics.py` (`Topic(slug, label, landing_key)`); `seed_story` and the admin
form refuse a slug that is not there, so a tag always means the same page. A topic whose
`landing_key` names an entry of `SEO_LANDINGS` links both ways: the story page shows it as a chip
linking to the landing, and `render_seo_landing` puts the published stories carrying it into the
landing's "From the field" block (`partials/_topic_stories.html`, included before the FAQ on all
12 landings; nothing renders for the alternatives pages, which own no topic). A topic without a
landing is a plain chip and a candidate page for epic #257. `/stories/?topic=<slug>` filters the
index; its canonical stays `/stories/`. Production stories seeded from the ops repo are tagged in
the admin. A new landing page gets its topic by setting `landing_key`, never by a second list.

**Mobile-adaptive layouts (two kill switches)**: `MOBILE_EDITOR_NAV` gives the editor
two-level contextual navigation below 768px: top strip = page tabs, bottom bar = panes of
the active page — Survey and Public results share the Structure/Edit/Preview vocabulary,
Responses gets Overview/Map/Responses/Perf under `RESPONSES_V2` (legacy switch-off:
Table/Map/Charts/Perf) (chrome in `editor/partials/_mobile_nav.html` +
`css/editor-mobile.css` + `js/editor_mobile_nav.js`; double-gated by the
`mobile-nav-enabled` body class AND the media query, so desktop is untouched; the Preview
pane is a full-screen overlay with a back button). `EDITOR_AUTOSAVE` replaces Save/Apply on
question EDIT forms with debounced autosave + a loud saved/saving/error indicator on ALL
viewports (autosave POSTs carry `autosave=1`, validation errors return 422 JSON so the
typed-in form is never re-rendered); new-question forms keep an explicit Create button.
Both default ON since PR #108 (owner decision); setting the env var to
False serves the pre-change layout, which is the rollback story. The RESPONDENT
survey page was deliberately left as-is: a bottom-sheet variant was built, reviewed and
REMOVED (2026-08-23) — the owner kept the legacy panel/crosshair flow; do not reintroduce
a sheet without an explicitly approved respondent-flow mockup. Touch reorder uses
SortableJS `delay:300 + delayOnTouchOnly` (long-press) — do not add ▲▼ reorder buttons.
Leaflet.draw tooltips pick tap-phrased strings via `pointer: coarse`
(`survey/templatetags/i18n_extras.py`).

**Registration abuse prevention**: `/accounts/register/` is served by `AbuseProtectedRegistrationView` (subclass of `AsyncEmailRegistrationView`). Three layered defenses run in order: honeypot field `website` (silent fake-success redirect), per-IP rate limit (`django-ratelimit`, fail-open on Redis outage), Cloudflare Turnstile siteverify (fail-closed on network error, dev-bypass when `TURNSTILE_SECRET_KEY=""`). Helpers in `survey/abuse.py`. Audit log in `AbuseEvent` model. Real client IP via `survey.middleware.CloudflareIPMiddleware` reading `CF-Connecting-IP` only when `CLOUDFLARE_TRUSTED=True`.

**Content screening (phishing hold, change `phishing-content-review`)**: registration defenses stop
bots; `survey/content_screening.py` is for the human who publishes an "XFINITY — click here" page on
our domain. `screen_survey(survey, trigger=…)` runs at the moments creator text goes live —
`editor_survey_transition` to `published`, `editor_publish_draft` (on the CANONICAL survey) and the
live saves of `redirect_url`/`thanks_html` and, since `edit-live-survey`, of question and section
text on a published survey (all through `_rescreen_if_live`) — and NOWHERE else: drafts and
`testing` are not screened. `collect_text()` gathers name, section/question text with translations,
thanks page and `redirect_url`; `score()` is pure (no DB, no network) over the signal table at the top of
the module (`WEIGHTS`, shorteners, trackers, brand terms, lure phrases, padding, ≤1 question, account
age, disposable domain) — a new incident is a row there, never a new code path. At or above
`CONTENT_SCREENING_HOLD_THRESHOLD` (7, calibrated on the 2026-10-02 scan: incidents 19 and 8, best
legitimate 5) the survey keeps `status='published'` but gets a `ContentReview(status='pending')`;
`check_survey_access` then serves the same 404 `survey_unavailable.html` an unknown UUID gets, the
creator sees a calm banner with NO reasons, and `ABUSE_REVIEW_EMAIL` (default `CONTACT_EMAIL`) gets one
mail with a signed link to `/editor/abuse-review/<token>/`. **Nothing bans automatically**: the staff-only
page's Release / Confirm phishing are POSTs (mail scanners prefetch GETs), and `confirm_phishing` is the
one place that deactivates an account, closes its surveys (audit rows), kills its sessions. A `cleared`
review remembers the content `fingerprint`, so a released survey is re-screened only when its text
changes. Screening fails OPEN (any exception → logged, publish completes), the notice falls back to a
synchronous send if the broker refuses the task, and `CONTENT_SCREENING=False` stops new holds without
releasing existing ones (that is the owner's click, or the admin). Respondent pages carry the
`_abuse_footer.html` notice + `/surveys/<uuid>/report/`; a report opens a `reported` review that holds
nothing. Every hold/release/confirm/report writes an `AbuseEvent(defense='content_screen')` with ids only.

**Terms, privacy and ownership (change `dpga-readiness`)**: `/terms/` (`views.terms_page`,
`terms.html`) is the Terms of use plus the Acceptable use & safety policy; `/privacy/` is a 301 to
`/trust/`, which carries the `#ownership` block (owner: Artem Koniukhov). The Digital Public Goods
Alliance application links these pages as evidence, so the section ids on `/terms/` (`terms`,
`acceptable-use`, `prohibited`, `moderation`, `harassment`, `children`, `personal-data`, `contact`)
and `/trust/#ownership` must not be renamed, and every sentence there must stay true in production —
change the policy text when the behaviour changes. Bump `TERMS_UPDATED` in `views.py` whenever the
text of `terms.html` changes. Sign-up requires `accept_terms` (16+, self-declared, nothing stored).
Report reasons live in `content_screening.REPORT_REASONS`; a `child_abuse` report always mails the
moderator with an `[URGENT]` subject, even on a survey that already has an open review.

**Russian homepage and hreflang (change `ru-landing-hreflang`, issue #248)**: `/ru/` is the
homepage rendered by `views.index_ru` under `lang_override('ru')` — one route, NOT `i18n_patterns`,
and `ru` stays out of `LANGUAGES` (the creator catalog is incomplete). `home_path` and `page_lang`
in the context tell `base_landing.html` which twin it is rendering: brand/anchors stay on `/ru/`, the
EN/RU switcher shows only on the pair, `<html lang>` comes from `page_lang` (there is no i18n context
processor, so `LANGUAGE_CODE` is empty in templates). Every `base_landing` page emits `hreflang`
`en` + `x-default` for itself; `landing.html` overrides that with the `en`/`ru`/`x-default` triple,
which the sitemap repeats as `xhtml:link`. `RussianLandingHreflangTest` fails when a homepage msgid
has no compiled `ru` translation — a new `{% trans %}` on the homepage needs its Russian in the same
PR. Sitemap/robots URLs come from `_public_base_url` (`X-Forwarded-Proto`, else `SITE_URL`'s scheme
on its host), because `request.scheme` is `http` behind the proxy.

**Acquisition metrics (top of the funnel)**: search impressions and clicks, landing visits and the
channel mix are read on the PostHog **AARRR** dashboard (`POSTHOG_AARRR_DASHBOARD_URL`, project
248938 dashboard 941308), where Google Search Console and Bing Webmaster Tools are native warehouse
sources (`googlesearchconsole_*`, `bingwebmastertools_*` tables). Nothing in this application
fetches or stores provider metrics any more — the former `sync_acquisition_metrics` command,
`AcquisitionDaily`/`AcquisitionSyncState` and the `mapsurvey-acquisition-sync` cron were retired
(change `acquisition-instrumentation`). Two rules for every HogQL over those tables: filter
`country != 'mar'` (38% of impressions are Moroccans searching a namesake app) and keep marketing
pages apart from `/surveys/` and `/r/` (those impressions are customers' respondents finding their
own survey). GSC data exists only from 2026-07-03, when the property was created. The staff funnel
dashboard at `/admin/survey/funnelreport/` keeps what only our database answers: registrations in
the window, registrations by first-touch source, and demo opens — total from `SurveySession` on the
`DEMO_SURVEY_URL` survey (retroactive), anonymous/signed-in split from `DemoOpen` (forward-only;
the user FK lives there and never on `SurveySession`, which must not link customers' respondents to
platform accounts). Demo helpers live in `survey/demo.py`.

**Signup attribution**: `FirstTouchMiddleware` writes a signed 90-day first-party cookie (`ms_ft`)
on the first marketing-page response — referrer host, bucket, UTM triple, landing path, no
identifier — and never on `/surveys/`, `/r/`, the editor or admin. `persist_signup_attribution`
reads it at registration (legacy session values as fallback) and never the request's own referrer,
which is the site itself. `classify_source` in `survey/events.py` buckets referrers as `email`,
`ai` (ChatGPT, Perplexity, Gemini, Claude, Copilot), `search_other` (DuckDuckGo, Brave, Yahoo,
Ecosia…), `google`, `bing`, `social`, `other`/`direct`; an AI `utm_source` promotes a direct visit to
`ai` because ChatGPT tags links with `utm_source=chatgpt.com` and often sends no referrer. The row
reaches PostHog as `$set_once` person properties (`first_source_bucket`, `first_referrer_host`,
`first_utm_*`, `first_landing_path`) on `creator_registered`; `sync_posthog_person_properties
--reclassify` repairs and backfills existing rows.

**First response and distribution events**: `SurveySession.opened_by_kind` (`external | owner |
collaborator | preview`) is set from the signed-in user's relation to the survey, never from
anything about an anonymous visitor. `survey_first_response` fires only for the first `external`
session. Creator events `share_link_copied`, `qr_shown`, `embed_copied` (browser, guarded by
`window.posthog`) and `responses_viewed`, `data_exported` (server) carry `survey_id` and a surface
only — never a slug or URL.

**Internal product analytics (PostHog)**: client-side snippet in
`survey/templates/partials/_analytics.html`, gated by `POSTHOG_PROJECT_KEY` (empty default = nothing
renders, which is what keeps tests, local dev and PR previews out of the production project) and
`POSTHOG_API_HOST` (Cloud EU). It measures **us**: which creator-facing screens get used, where
activation leaks. Plausible was removed in September 2026; respondent pages load no third-party
analytics script at all.

**Two hosts, on purpose.** The browser initialises against `POSTHOG_CLIENT_HOST` — a first-party
hostname CNAME'd to PostHog's managed reverse proxy, because `eu.i.posthog.com` is on every
mainstream blocklist and our creator audience runs blockers more than most. The server-side client
(`survey/apps.py`, and through it the middleware and the Celery receiver) keeps using
`POSTHOG_API_HOST` directly: no ad blocker runs inside our containers, so proxying error capture
would only add a DNS record and a CDN edge to the subsystem that must survive an outage. Empty
`POSTHOG_CLIENT_HOST` falls back to `POSTHOG_API_HOST`, and that fallback lives in the context
processor rather than in `settings.py` — resolving it at import time would freeze the value and
leave the browser on a stale host whenever the API host is overridden. `ui_host` is pinned to
`https://eu.posthog.com` because a custom `api_host` leaves the SDK unable to find the PostHog app.
Note the snippet derives its asset host by string-replacing `.i.posthog.com`, which is a no-op
against a proxy domain — so `array.js` correctly loads from the proxy too.

Two rules that are easy to get wrong:

- **PostHog never loads on respondent surfaces.** Two settings enforce one rule, both read in
  `survey.context_processors.analytics` — *not* by omitting the include from
  `base_survey_template.html`, since an omission would be invisible in review and a new base
  template would inherit whatever its author happened to copy.
  `POSTHOG_EXCLUDED_PREFIXES` (`/surveys/`, `/r/`) covers respondent URLs.
  `POSTHOG_EXCLUDED_VIEW_NAMES` (`editor_section_preview`, `editor_survey_thanks_preview`) covers
  the ones no prefix can express: the editor's Live preview frames a real respondent page served
  from under `/editor/`, where the surrounding page *is* tracked. That iframe used to run a
  second PostHog client in the creator's tab — one session with two recorders, so session replay
  alternated between the iframe's ~470px viewport and the editor's ~1600px one, and 1169 of 1799
  editor `$pageview`s over seven days were iframe loads rather than people. `_analytics.html` also
  refuses to `posthog.init()` when `window.top !== window.self`, which catches framed surfaces
  added after the view-name list. `editor_question_preview_live` and `public_results_preview`
  render standalone templates that include no analytics partial, which is why they are absent
  from the list — a new preview view that extends a base template must be added to it.
- **`SurveyEvent`/`TrackedLink`/`survey/events.py`/`PerformanceAnalyticsService` are a different
  system and must never be folded into PostHog.** They measure our *customers'* respondents on the
  customer's behalf (section funnel, referrer buckets, UTM campaigns, page load) and are a feature we
  sell. That data stays in our database. The two answer superficially similar questions about
  entirely different people.

**Error tracking (PostHog, same key)**: three capture paths — Django view exceptions via
`posthog.integrations.django.PosthogContextMiddleware` (in `MIDDLEWARE` after auth), Celery task
failures via the `task_failure` receiver in `mapsurvey/celery.py`, and client-side JS exception
autocapture (a PostHog project setting, not a template change). Unset key = the client is explicitly
disabled in `survey.apps.SurveyConfig`. Errors on `/surveys/`/`/r/` ARE captured (they are our
defects) but scrubbed by `_posthog_scrub_tags` in `settings.py` — no respondent IP/user-agent, URL
truncated to the prefix; `/admin/` and `/__debug__/` are not captured at all. The `posthog` package
is pinned `~=6.9`: 7.x needs Python ≥3.10, and 6.7.5–6.7.13 shipped with silently broken Django
exception capture — canary tests in `PostHogErrorTrackingTest` guard both directions.

### URL Structure

- `/` - Redirects to login or editor
- `/editor/` - Dashboard for authenticated users
- `/surveys/` - Public survey list
- `/surveys/<name>/` - Survey entry (redirects to first section)
- `/surveys/<name>/<section>/` - Survey section form
- `/surveys/<name>/download` - Export data as ZIP
- `/r/<slug>/` - Public survey results page (aggregated, read-only)
- `/admin/` - Django admin (surveys configured entirely here)

### Environment Variables

Required in `.env`:
- `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Database: `SQL_ENGINE`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`, `SQL_HOST`, `SQL_PORT`
- Optional S3: `USE_S3=TRUE`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`
- `POSTHOG_AARRR_DASHBOARD_URL` (optional): where the staff funnel dashboard sends readers for
  top-of-funnel numbers; defaults to the production PostHog dashboard.

### GeoDjango Notes

- Database engine must be `django.contrib.gis.db.backends.postgis`
- Models use `PointField`, `LineStringField`, `PolygonField` from `django.contrib.gis.db.models`
- Admin uses `LeafletGeoAdmin` for map-based editing
- Custom Leaflet draw widgets in `survey/forms.py` for frontend geometry input

## Workflow: Spec Driven Development (OpenSpec)

This project uses **Spec Driven Development** via the `openspec` CLI. All changes go through the artifact pipeline:

```
/opsx:new → /opsx:ff or /opsx:continue → /opsx:apply → /opsx:archive
```

**Key rule**: When asked to make changes or fix bugs, **always work through OpenSpec first**:
- If there is an active change related to the request — update its specs/design/tasks before editing code
- If no relevant change exists — create a new one (`/opsx:new`) before implementing

Never jump straight to code without a corresponding change in `openspec/changes/`.

## Public repo vs. private ops repo

This repository is **public**. Everything about running the business — outreach dossiers,
customer stories, cohorts, GTM plans, competitor notes, requirements, raw notes, the DPA
draft, the outreach sender — lives in the private repo `ganjasan/mapsurvey-ops`, checked
out at `../Mapsurvey-ops` (layout mirrors the old in-repo paths: `docs/marketing/...`).
Code reads it only through `settings.OPS_DIR` (env `MAPSURVEY_OPS_DIR`), and only from
tooling; tests that need it skip when it is absent. The main checkout has gitignored
symlinks (`docs/marketing`, `raw`, `requirements`, …) into it for convenience.

- People are named in this repo only by pseudonym `lead-NNN`; the key is
  `../Mapsurvey-ops/redaction/redaction-map.json`. Never paste a name, email, username
  or dossier excerpt into `openspec/`, a commit message or a PR — write `lead-NNN`, or
  describe the role ("a city planner in Berlin").
- `RepoHygieneTest` fails when a real email address lands in a tracked text file.
- Story data, respondent exports and ZIPs never enter git at all — not even the ops repo.

## Project Management

**Task list**: See `TODO.md` for planned features and tasks
