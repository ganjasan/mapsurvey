# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Docker (recommended)
docker-compose up --build              # Start all services
docker-compose up db                   # Start only PostgreSQL/PostGIS

# Local development (venv in ./env)
source env/bin/activate                # Activate virtual environment
pipenv install                         # Install dependencies (Pipfile — there is no requirements.txt)
python manage.py migrate               # Apply database migrations
python manage.py runserver             # Start development server (port 8000)
python manage.py createsuperuser       # Create admin user
python manage.py collectstatic         # Collect static files

# Testing (requires running PostGIS on port 5434)
./run_tests.sh survey                  # Run all survey app tests
./run_tests.sh survey -v2              # Verbose output
./run_tests.sh survey.tests.SmokeTest  # Run specific test class
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

**Test location**: `survey/tests.py`

**Writing tests**: Use `django.test.TestCase` and GIVEN/WHEN/THEN pattern for docstrings.

**Redis**: a few tests (`LastActivityMiddlewareTest`) exercise cache-gated code and need
Redis on `localhost:6379`. `run_tests.sh` does not start it; without it those tests fail
with `UserActivity.DoesNotExist`.

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
our domain. `screen_survey(survey, trigger=…)` runs at the three moments creator text goes live —
`editor_survey_transition` to `published`, `editor_publish_draft` (on the CANONICAL survey) and the
live saves of `redirect_url`/`thanks_html` (`_rescreen_if_live`) — and NOWHERE else: drafts and
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
