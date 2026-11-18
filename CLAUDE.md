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
`IntegrityError`s. `pypdf` (dev package) reads the printable-form PDFs back; `reportlab` writes
them (both since change printable-form — a venv from before needs `uv pip install reportlab pypdf`). Views leave `translation.activate()` behind, so the runner resets
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

**Question Types**: `text`, `text_line`, `number`, `choice`, `multichoice`, `range`, `rating`, `datetime`, `point`, `line`, `polygon`, `image`, `html`, `budget`

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

**Printable paper form (`survey/print/`, change `printable-form`, #489; epic #350 item 2)**: the
Share page's *Print a paper form* (every status, every plan, `editor` role) downloads
`/editor/surveys/<uuid>/print/form/?lang=&paper=` — `pdf.build_form` walks the RESPONDENT structure
(`compute_visibility(surface='respondent')`, `group_runs`; operator-only items left out, rules as an
"Answer only if …" line) and renders one `QUESTION_SHAPES[input_type]` flowable per question in
reportlab (pure Python; the bundled DejaVu fonts in `survey/print/fonts/` cover everything but CJK).
A map section prints a frame from `static_map.render_frame`: the Mapbox **Static Images** API for the
basemap (same token, a separate metered SKU, cached a day per frame, fail-soft to a gridded empty
frame) with the survey's reference layers drawn on it by Pillow, then a letter legend (A ●, B ━,
C ▭, D ░ — never icons: they do not survive a photocopy) and a sub-question table per mark. Every
page carries four 6 mm alignment squares and a **form code** — two vector QR (20 mm, level H, both
bottom corners) with payload `MSFORM:<form>:<copy>:<page>:<pages>` (copy 0 = unnumbered; the old
`ms:form:…` still parses, `print/form_code.py`) and the line `MS-<form> · #<copy> · Page n of N` —
that names a `PrintedForm` row — version, language, paper,
`structure_hash`, and per page the map frame's rectangle in mm plus its geographic bounds — which is
what item 4 (photo marks → coordinates) will read; a reprint of an unchanged survey reuses the row.
Fixed form strings come from the RESPONDENT catalogs (75; `test_every_printed_form_string_is_translated_in_every_catalog`),
the dialog's from the creator ones. Event `form_printed` is server-side. The flyer generator #220
is the next consumer of the same page template and static map. `PrintedForm.layout[page]["items"]`
(since change `paper-photo-entry`) lists what starts on each page — `ItemMarker` flowables record it at
draw time — so a photographed page is read against exactly those questions; the walk both share is
`survey/print/structure.py::plan_items`. **Numbered copies** (`?mode=copies&copies=N`, 1…200, the
dialog's default; `mode=single` = one copy to photocopy): `PrintRun` hands out copy numbers per
CANONICAL survey under `select_for_update` on its header — they only grow, across forms, languages
and papers, so a copy number names one questionnaire forever. The form is laid out once;
`_CopiesCanvas` stores each body page as a Form XObject and stamps every copy's codes over a
`doForm` (20 copies ≈ one copy in bytes). Never print copies by re-running the layout or by merging
PDF pages: both were tried and were slow or huge. `LAYOUT_VERSION` in `pdf.py` enters the structure
hash — bump it when the page chrome changes. `?keep=1` (the dialog's default) wraps a map section's
heading, frame, legend and marks tables in one `KeepTogether` and is part of the hash too; file
questions are not printed at all (`structure.plan_items` drops `FILE_INPUT_TYPES`).

**Paper forms from photos (`survey/paper/`, `survey/paper_views.py`; change `paper-photo-entry`, #495;
epic #350 item 3)**: *Responses → Enter a response ▾ → From photos of paper forms* opens **Paper
responses** (`/editor/surveys/<uuid>/responses/paper/`, the operator-entry gate). The operator's unit
is the **paper response** (`PaperSheet`, labelled "Copy 37" / "Response 4" by `.label` — no surface
says sheet or batch); `PaperBatch` is a hidden per-survey inbox (`paper.inbox_for`) that only holds
counters. Rows: `PaperUpload` (one file as received, plus where it was dropped: `sheet`,
`expected_page`, `is_pdf`), `PaperPage` (one JPEG ≤ 2200 px on the PRIVATE tier with its code),
`PaperSheet`, `SurveySession.paper_sheet`. **The code decides, never the order of arrival**
(`survey/paper/sheets.py::place_page`): a numbered copy's page goes to that copy's response (unique
per inbox) whatever card it was dropped on; an unnumbered page goes where the operator put it (*New
response*) or to its PDF's response (one PDF = one form); a loose unnumbered photo, a page of a stored
response or of another form is set aside with a reason; a second photo of the same page wins and the
first is `replaced` (restorable), and once the new photo is read `review.supersede_machine_answers` drops the stored rows that still equal the earlier reading (the operator's edits stay). The first build grouped by upload order and split one form into two
sessions — do not bring order-based grouping back. **No model ever reads a code**: zxing-cpp decodes
it locally, at full resolution in ingest (PDF at 200 dpi) and once more on the stored JPEG. **The web
process never decodes a byte**: the upload view hands the file to storage and enqueues
`ingest_paper_upload`; `survey/paper/ingest.py` and `recognise_paper_page` (place, then
`check_quota(org, 'paper_page')`, then ONE vision call per page bounded by the page's `items`,
`extract.py` + `prompts.py`) run in Celery — on the dev stack the worker does not reload, restart it
after touching this code. Gemini counts thinking tokens against `max_tokens` (extraction uses 16000; a
200-token call came back empty). `LLMProvider.complete_structured(images=[(mime, bytes)])` is the only
way an image reaches a provider. Every call is an `AIGenerationEvent(kind='paper_page')` and an
immediate `$ai_generation` (trace `paper-response-<id>`, `survey/paper/accounting.py`) — PostHog
prices it; nothing stores dollars. The check is page by page of the PRINTED form
(`paper_response_page`): photo left, the questions printed on that page right (`_page_plan` over
`layout[n]["items"]`, `questions_filter`, `save_section_answers(only_questions=)` so a section split
over two pages keeps both halves), a stepper, prefill through `_build_section_context(prefill=…)`
(stored rows always win), doubtful (`confidence < PAPER_DOUBTFUL_CONFIDENCE` or `unreadable`) and
blank fields marked, a missing page attached in place; forms without an item map fall back to the
section flow of operator entry. **Marks on the printed map (item 4, `survey/paper/marks.py`)**: on a
page with a map frame the same call lists the frame section's geo questions with their legend letters
(`print/structure.py::mark_letters`, shared with the printer) and returns `marks` (label, question,
vertices in 0–1000 of the photo, the table row's answers) plus `map_frame`; registration is LOCAL —
`find_frame_fiducials` (the 5-mm squares printed in the margins beside the frame: corners since
`LAYOUT_VERSION = 3`, mid-sides too since 4; `fiducials`/`fiducial_dx_mm`/`fiducial_mids` in the frame
record, targets from `fiducial_targets`) first, then
`find_alignment_squares` (page corners, pure Pillow at full resolution, thresholds strict → loose,
solid through — a QR finder centre is not a square — and a portrait quadrilateral), then the model's
`map_frame_corners` (a trapezoid), then its box; one weighted least-squares homography over every
landmark (`fit_registration`: fiducials ×50 when ≥ 3, else ×4; page squares ×1; the frame's border
sampled all around by `find_frame_edges` ×10 and its corners from the fitted lines ×30) PLUS a
thin-plate spline over the residuals, because paper on a lap is not a plane — `apply()` takes the
`{h, tps}` registration. A page also bows INSIDE the frame where no border can see it, so the
printed map is the last landmark: `survey/paper/texture.py` matches patches of the frame image kept
at print time (`texture.save_reference` → `paper_refs/<form>-<page>.png` on the private tier,
`ref_key` in the frame record; forms printed before it re-render, the grid stand-in never) against
the photo rectified through the current registration (FFT normalised cross-correlation at a 6×4
grid of anchors, ×20, up to three match → refit rounds in `_refine_with_interior`); edge samples
are re-anchored along their side on every refit (`_fit_with_edges`), since across the side they
pin the paper and along it they only repeat the plane they were found with. For a `point` question
the vertex is then moved onto the ink (`texture.snap_to_ink`: rectified photo minus reference, the
nearest blob 0.8–4.5 mm within 7 mm with discness ≥ 0.5; letters fail it) — the model answers
with the label beside the dot often enough that its vertex is a hint, not the answer. **The hybrid
(`survey/paper/ink.py`)**: with a reference image the GEOMETRY of every mark comes from the ink —
coloured against the paper around it (a blue pen: channel shares less their 8-mm mean) or darker
than the paper's 8-mm and 3-mm means and than the darkest print within 3 px (a black pen), never on
near-black print — not HSV saturation, not absolute chroma, not darkness alone (each failed on one of
the two copies; `design.md`) — its components read as hatched cluster → spray, filled disc → point, closed loop → area,
long stroke → line (pieces sewn across skips, an outline whose ends meet closed), glyph-sized rest →
writing — and the model only NAMES them: `_match_marks` pairs each model mark with the ink of its
kind along its vertices, ink the model missed becomes a numbered mark at confidence 0.5, a model
mark the ink lacks keeps its vertices at 0.6, and ink under the model's `label_box` is writing.
Never make the model's vertices the geometry again where ink is available. `mm_to_lnglat` goes
through the frame record's Mercator bounds (linear in world pixels, never in degrees). The
prompt asks for the symbol's ink, never the label beside it. The result is GeoJSON features in the `existing_geo_answers` shape, which
`_build_section_context` restores onto the map from `prefill` (never into `initial`), and
`_page_plan` gives a section's geo questions to the page with its frame and to NO other page — an
empty POST of the heading's page would wipe the placed marks. That page (`paper_map_mode`) is NOT the
respondent panel: form layout half and half, `_paper_marks.html` + `js/paper_marks.js` draw the
printed frame as their own Leaflet map and the marks TABLE the paper has (rows A1…An, the
sub-questions as columns), and a hidden input per geo question posts `feature|feature` in the dialect
`save_section_answers` parses (`views.geo_answer_features` is the one builder of that feature shape).
On paper, `pdf._sub_cell` prints a choice column's boxes in EVERY row. A table that runs onto the
next page (`extract.table_items_for_page`: the frame's page up to the page of the question's own
`question:<code>` marker, which follows the table on paper) is asked for there as rows without
geometry (`marks.table_rows`, a `rows_only` field); `merge_pages` hangs them on the map page's field
as `rows_extra` and `_paper_map_context` joins them to the marks by label — a label with no mark is an
`unplaced` row the check shows filled, with a place-it link. Images go when a response is
stored (`delete_sheet_images`) or the response is deleted (`sheets.delete_sheet`: an open response goes whole, its copy number free again — there is no "skipped"), and by `sweep_paper_batches --delete` (in `reclaim.sh`, deletes
open responses idle past `PAPER_BATCH_TTL_DAYS` the same way; stored rows stay). Export column `paper_copy`. Events:
`paper_response_created`, `paper_page_recognised`, `paper_sheet_entered` (`fields_changed` vs the
prefill = the reader's quality signal) — ids and counts, never content.

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

**Budget questions (`survey/budget.py`, `survey/budget_stats.py`, change `budget-question`, #447)**: ONE
question type and ONE group setting — never a geo type (the first build had one, `budget_items`, and
the owner rejected it: "keep the geo questions as they are, just give each object a price"). `budget`
(a `CHOICE_TYPES` member, NOT geo) has a `mode` — `split` (amounts per item that add up to the
budget) or `projects` (pick items until the budget is spent) — and stores ONE `Answer` per respondent
in `Answer.allocation = {"total", "items": {code: amount}}` (Projects: the cost at answer time);
`selected_choices` is never set, so no choice consumer picks a budget up. Settings live in
`validation_settings['budget']`; items are `choices` with the extras `description`, `cost`,
`description_i18n` (and the icon grid's `icon`/`color` — the bar is stacked per item in the item's
colour, a group member's `Question.color`) capped in `normalise_choice_extras`; `source == 'layer'` takes the items from
`Question.layer`'s objects (cost from `cost_property`) and joins `layers.section_layer_ids`. **A budget
on the map is a GROUP**: `QuestionGroup.budget = {total, unit, symbol}` (group dialog, empty total =
ordinary group) and a PRICE on each member geo question, `validation_settings['price'] = {amount, per}`
with `per` ∈ `feature | length | area` narrowed by type (`budget.PERS_BY_TYPE`; the Price block shows in
the question dialog only inside a budget group). Creators find it in the "New question" picker: the
**Budget group** card in Map questions is a picker ACTION (`question_types.PICKER_ACTIONS`, not an input
type — the parity test is about `PICKER_TYPES`) that posts `budget=1` to `editor_group_create` and opens
the group dialog, which reads "Budget group" with its own tips. The geo questions keep everything else. One validator
for every record (`normalise_budget_settings(…, input_type | 'group')`, `normalise_price`), one cost
(`feature_cost` = amount × `measure`: 1 / metres / m² in Web Mercator corrected by cos(lat) like
`spray.cloud_area_m2`; the browser mirrors it with `distanceTo` / `L.GeometryUtil.geodesicArea`). The
section POST has no error path for budgets either: `budget.parse_submission` stores nothing for an
impossible allocation, `views._enforce_group_budgets` admits a group's marks in stored order
(`budget.GroupSpend`) and deletes the rest, and the client (`js/budget_question.js`: `refreshGroups`
from `refreshGeoQuestionUI`, `admit` from `draw:created`, `firstInvalid` from Next) says why — no new
placement path. Aggregates: `budget_stats.aggregate` (question) and `group_aggregate` (group; Responses
inserts a `budget_group` block before the group's first member); export writes a `cost` property per
priced mark and a `<group>: spent` column. Budget groups are FREE on every plan (owner 2026-11-10); Pro feature
`budget_map` is asked only where a budget question becomes layer-sourced (`services.questions.
_budget_pro_gate`) → `ProRequired`; respondents never meet it. A group's total/unit, a question's
price, and a budget question's mode/total/unit/step/source/cost property/item costs are structural on
a live survey (`versioning._budget_structural_changes`, `services.groups.update`).

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
(300 / 10 min). Event `mcp_tool_called` (tool, outcome, token id; never arguments). Next to it
`mcp/analytics.py` emits PostHog MCP Analytics' own format (`$mcp_tool_call`, `$mcp_initialize`,
`$mcp_tools_list`, change `mcp-analytics-events`, #649) — the SDK is Node-only; client name/version
ride in the signed session id, `$session_id` is a UUIDv7 derived from it, and `$mcp_parameters`,
`$mcp_response`, `$mcp_intent` and error `detail` are never sent (`$mcp_error_message` = our code). The help page
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

**Sites (`/p/<slug>/`, epic #348; called "Landing pages" until 2026-11-09)**: a workspace's public
site for an engagement — a landscape/planning firm's project site or a council's — built from a
CLOSED set of blocks (`survey/sites.py::BLOCK_KINDS`, one cleaner per kind in `clean_block`, one
public template `sites/blocks/<kind>.html`, one canvas include). Models `Site`, `SiteSurvey`
(surveys linked many-to-many), `SiteBlock`, `SiteFile`, `EventRegistration`; Pro feature `sites`
(trial: one site), a published site survives a lapse. The builder (`site_views.py`,
`templates/sites/builder.html`, `js/site_builder.js`) is the page as visitors see it: the panel form
(`sites/_block_form.html`) is the ONE serialisation of a block, canvas edits travel in its hidden
fields, every change autosaves with `autosave=1` (JSON fragments; an EMPTY field waits, a wrong value
is a 422). Owner rules: a block's primary actions happen in the block, refinements in Settings; reuse
the app's dialogs and toolbars (no `confirm()`). **Every write goes through `survey/services/sites.py`**
(change `sites-service-layer`, #617) — `SiteServiceLayerTest` fails if a view writes a row itself.
Never name a template context variable `block` in a template extending a base (it is a `BlockNode`);
the builder uses `b`/`edit_block`. CSS prefixes `lp-` (public) / `lb-` (builder) are historical
internal names; the marketing `css/landing.css` and the SEO landings are a different thing. Plan of
the next waves: ops `requirements/design/sites-v1.1-architecture-and-plan.md`.

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
`api` 500, `unbranded` 1, `pro_help` 1, `operator_entry` `None` = uncapped (counted, never refused;
the paper cap arrives with #495) (`TRIAL_ALLOWANCES` in `billing/features.py`; empty = not offered,
the rollback). One trial per OWNER (partial unique on `claimed_by`) and per workspace; never on Pro;
AI generation is not in it (free on every plan). **It starts itself (change `pro-trial-auto`, #508)**:
the first Pro use anyone allowed to make it makes in a workspace that never had a trial creates the
grant for the earliest-joined owner without a trial (`started_by` = the actor, `trigger` = the
feature key; a click is `trigger='click'`) and counts that use — never at registration or workspace
creation. Every control that OFFERS a use asks `billing.trial.may(org, key)` (= `Entitlements.may`
or `startable`), every point of use calls `billing.trial.use(org, key, actor)` (start + count),
never `consume` directly; the view then calls `trial.flash_started(request, org)` for the one-time
notice. The owner gets a start mail (on commit) and one "ends in 7 days" mail
(`notify_trials_ending`, daily from `reclaim.sh`, `ending_notified_at`). **Every Pro control carries
`{% pro_badge org "key" %}`** (`billing/_pro_badge.html`, `css/pro_badge.css`, violet `--pro`
tokens — teal is for actions): plan / trial / startable ("free to try") / locked; never hand-write a
Pro label. Navigation items (the sidebar) use `{% pro_nav_mark org "key" %}` instead (change
`onboarding-friction`, #638): nothing unless the workspace is `locked`, then a grey lock without the
word — a "PRO" in the sidebar read as "not for you" to the Free creators the trial is for. Tests that need a Free workspace REFUSED call `billing.tests.helpers.trial_used_elsewhere(org)`.
`pro_help` is "Advice on your survey and results" (#438), listed in every menu below a free "Suggest
an idea or report a bug" (`billing/_help_entries.html`). The webhook still owns
`Subscription`; a grant is a different row with a different writer. **Three questions on
`Entitlements`**: `has(key)` = the PLAN includes it (plan cards, `is_pro`, lapse task); `may(key)` = a
NEW use is allowed (plan, or a live trial's remainder) — wrapped by `trial.may`, which every gate
uses (`require_feature`, `require_pro_api`, `pro_organizations`, `SurveyHeaderForm.unbranded`);
`covers(key)` = in force (plan, or a live trial includes it, spent or not) — what `{% has_feature %}`
answers, because a survey unbranded under the trial stays unbranded after its one switch-off is
spent. A use the plan does not cover is counted ONLY by `trial.consume()` (through `trial.use`) — one
`UPDATE … WHERE ("limit" IS NULL OR used < "limit") RETURNING`, race-safe — at the point of use:
`require_pro_api` (once per request per workspace; `mcp.protocol.call_tool` resets the memo per tool
call), `services.surveys.update_settings` (a badge switch-off, inside the service transaction),
`org_help` (a stored request), `operator_entry_views.entry_header` (one sheet; the sheet's own pages
admit on `covers`). Expiry is a comparison, no cron. The viewer's state (`available | live | exhausted | expired |
used_elsewhere`) is `trial.state_for(org, user)`, rendered by `billing/_trial_offer.html`;
`pro_required` carries `trial: none|exhausted|expired`. Staff end a grant by setting `revoked_at` in
the admin; the counters are read-only there.

**Support chat (Chatwoot, change `chatwoot-support-chat`, #291)**: one partial,
`partials/_support_chat.html`, included by the three base templates; config and the signed-in
creator's identity come from `survey.context_processors.support_chat`. The identifier is
`str(user.pk)`, signed with `identifier_hash = HMAC-SHA256(CHATWOOT_HMAC_TOKEN, pk)` on the
server — the token never reaches the browser; empty `CHATWOOT_WEBSITE_TOKEN` = no widget, no
third-party request (tests, local dev, previews without the env group). The creator bases
include it with `editor_bubble=True` (change `onboarding-friction`, #638): the bubble shows on a
desktop and never below 768 px, carries our own "×" that hides it in this browser
(`localStorage['msSupportBubble']`), and "Show chat button" in the "?" menu
(`.support-bubble-restore`, `showSupportBubble`) brings it back. The editor widget never speaks
first, bubble or not: no unread pop-up; the "?" menu in the header (`editor/partials/_help_menu.html`)
and "Help & support" in the ⋯/account menus stay the entry points, and an agent reply lights the
`.support-unread` dot on them. `openSupportChat(event, context)` opens the chat and sends `context` to the agent as
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
(`default` = 420 px, `third`, `half`), plus where the content sits inside the panel (change
`panel-content-align`, #476): `content_width` (`full` | `column` ≤ 640 px, box-centred) and
`content_valign` (`top` | `middle` — auto margins, so a long section scrolls from its title, never
`justify-content: center`), both opt-in and ignored by `form`; and `keep_panel_open` (change
`keep-panel-while-drawing`, #477, map sections, desktop): placement paths never call
`toggleInfo(false)` themselves but `hidePanelForPlacement()`, and the crosshair, its pin position,
the draw bar and a moved point centre on `visibleMapArea()` — a new placement path must use both
(`test_placement_paths_go_through_one_helper` counts them). Map-less stages are ONE constant, `models.MAPLESS_LAYOUTS`
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
(`section_list_item`, `question_list_item`, a report block's toolbar in `reports/editor/_canvas_block.html`) and the toolbar/modal buttons
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
"+ New Survey" lead to the START PAGE `/editor/surveys/start/` (`editor_survey_start`) — two cards,
*Survey wizard* / *Start from scratch* — not to the create page. The third card (*Use your AI
assistant*) was removed in change `onboarding-friction` (#638): nothing on the first screen that
does not make a survey; the agent page is reached from the sidebar's *MCP* item, the "?" menu and
the help centre. Before the first survey (`app_nav.onboarding`: no canonical, non-trashed survey in
the active workspace; owner/admin/editor) workspace-level pages open the sidebar as the rail unless
the creator chose Expand (`msSidebar = 'wide'`).
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
the completion state, the v2 Responses page and `export.excluded_sessions` all go through it.
The v2 page hides empties unless the `rv2_show_empty` cookie is `1` (`analytics_views._show_empty`;
the legacy page and every other `SurveyAnalyticsService` caller keep `include_empty=True` and see
all sessions). `service.empty_count` feeds the "N opened without answering" line
(`editor/partials/_empty_sessions_toggle.html`). Response numbers `#N` come from
`service.sequence_numbers()` — rank among non-empty sessions; empty rows carry none — and
`comments.session_seq` follows the same rule. An empty row keeps its "Empty" badge and no marker. Exports
never contain empty sessions, whatever `include_all` says, and since `data-scope` neither does the
public results `response_count`; the funnel/Perf pane (`SurveyEvent`) still counts every session. The section POST treats
whitespace-only values as blank and stores text/number values stripped.

**Data catalogue (`data` app, change `data-catalogue`, #667)**: `data.models.Dataset` is a REGISTRY row
over data that stays where it is — `layer` (a creator's reference layer, FK), `shared_map`, `answers`
(a canonical survey's answers to one top-level geo question, by code across versions) and `responses`
(a survey's respondent rows). `data.datasets.sync(org)` creates/renames/drops rows idempotently and runs
when `/editor/data/` opens (a read-time sync cannot miss a write path); `catalogue_rows(org, user)`
filters by survey access (`visible_survey_ids`: org owner/admin/viewer see all, an editor their
collaborations) and counts through `data.scope`. Privacy defaults: collected kinds `aggregated`,
creator layers `public`. `data.features.question_features(survey, code, scope)` is the one reader of an
answers dataset as features. Sidebar item `data` in `app_nav.MODULES`; help `how-to/data/`.
**Uploads (change `data-upload`, #668)**: a workspace dataset needs no survey — `SurveyMapLayer.survey`
is nullable and `organization` says whose a layer is (set in `save()` from the survey for survey
layers, so no creation path has to). "+ New dataset" stores the file on the private tier and runs
`data.tasks.run_data_import` (once per job, file deleted after): `data.imports.open_source` reads
GPKG/zipped SHP/KML/GeoJSON with GDAL (reprojected to 4326) and CSV with `csv` (lon/lat, or British
National Grid by value range; anything else refused), profiles fields into `Dataset.fields`
(type, private for email/phone/name columns) and feeds `objects_from_features` in two passes.
Limits by plan in `data.tasks.limits_for` (Free 10 MB/5,000, Pro 50 MB/100,000). Uploads start
`private`; reaching a survey map is #670 and stays within the survey layer caps.
**Dataset page and private fields (change `data-metadata`, #669)**: `/editor/data/<id>/`
(`data.views.dataset`; visibility = the catalogue's `catalogue_rows`, edit = workspace editor+ and,
for a survey's dataset, survey editor+) holds the details (`theme` = DCAT-AP themes, `maintainer`,
`update_frequency`, `licence` from the closed list), the field dictionary
(`Dataset.fields[{name,label,type,description,private}]`, `data.fields.dictionary` merges stored
entries with `layer.property_names`) and the labelled CSV/GeoJSON download. **A private field never
leaves the dataset page and the object editor**: `data.fields.hidden_names(layer)` is applied in
`layers._object_props` (so the derived GeoJSON, every reader of it, and `property_names` — hence the
editor pickers — lose it), `build_map_layers_metadata` (label field, style rule), `style_summary`,
REST/MCP `object_out`, the ZIP's `serialize_layer_objects` and budget cost properties; a
`properties` write through `services.layers` keeps the private values the writer never saw
(`merge_private`). A new output of `LayerObject.properties` must go through `data.fields` too. Saving
a dictionary whose private set changed rebuilds the layer. The respondent card shows the public
dictionary fields by label (`object_card_payload['fields']`).
**Links (change `data-links`, #670)**: a dataset is LINKED, never copied — `data.models.DatasetLink`
(canonical `survey` OR `site_block`, plus the card `fields` a survey shows). `survey.layers.layers_for`
returns owned layers ∪ the layers of PUBLIC datasets linked to the canonical survey (subquery on ids),
so every read surface follows (respondent metadata, question layer picker, Responses, print, ZIP,
the gated endpoint `_gated_layer`); WRITE paths keep `owner.map_layers` / `survey=layer_owner(...)`, so
a survey never edits or deletes a layer it borrows — do not switch a write path to `layers_for`.
Guards are `data.links.link_refusal` (public only, survey caps 5,000/10 MB, 10 layers incl. links);
a linked dataset cannot go private; unlink/delete refuse while a question is bound. A Site map block
stores `data['dataset']` and the page fetches `/p/<slug>/blocks/<id>/dataset.geojson` (never inlined);
`services.sites.save_block`/`duplicate_block` keep its link row; `clone_survey` re-links. "Used by" =
`data.links.used_by` (dataset page, delete page `/editor/data/<id>/delete/`, catalogue count).
**Versions (change `data-versions`, #671)**: "Upload new version" is a `DataImportJob` with `target`;
`data.tasks.run_data_version` runs twice — preview (diff by the layer's `key_field`, keys derived by
`layers.derive_key`, counts + answers on removed objects in `report`, file kept, status `preview`) and
apply (status `applying`, recomputes the diff, updates matched `LayerObject` rows IN PLACE so their
`Answer.layer_object` survive, adds/removes, merges the field dictionary, rebuilds, writes a
`DatasetVersion`). Never replace objects by delete + create on a version: answers hang on the row.
Refused without a key field, above `limits_for`, or above the survey caps while linked into a survey.
**Views (change `data-views`, #672)**: `DatasetView(dataset, name, kind, conditions, fields, color)`, stable
across versions. `kind` follows the dataset — `objects` for a layer (conditions on PUBLIC fields, eq/in/gt/lt,
evaluated in Python by `data.dataviews.matches`; collection streamed with `layers._feature_json` keeping only
`kept_names`, cached per view/layer rebuild/view edit), `grid` for answers (`data.aggregate.grid` over
`SessionScope.public` with the survey's public-results K; polygons + masked counts only). `DatasetLink.view`
(RESTRICT): the survey's gated GeoJSON, object card and map colour go through `data.links.survey_view`; a Site
map block stores `data['view']`/`data['choice']` (`<dataset>:<view>`). A grid view is refused as a survey
layer.
**Analysis views (change `data-analysis-views`, #692; Reports epic #712)**: the kinds a dataset takes are ONE
table, `data.dataviews.kinds_for(dataset)` (first = default) — layer → `objects`; answers → `grid` + `coverage`
(line/polygon) or `density` (point/spraycan); responses → `engagement`, `crosstab`, `responses`. A new kind is a
row there plus a function in `data/analysis.py`, never a branch in a view or in Reports (Vision BO-4: Reports
computes nothing). `DatasetView.config` holds a kind's settings (cross-tab: `{rows, columns}` question CODES,
resolved by `data.questions.questions_of` — which `reports.sources` imports; Data never imports Reports for it).
`dataviews.result(view, lang)` is the one reader: steps + per-period series (`engagement`, every clean session —
"answered" equals the public response count), a table of distinct respondents (`crosstab`: cells in `0<n<K`
masked; the total of every line holding a masked cell AND the grand total are then withheld, since totals minus
visible cells would return the masked values), or grid cells (`coverage` adds `share`, `density` adds `marks`; `data.aggregate.grid` counts marks, K stays
on respondents). **There is no unmasked reading of a view**, for any role, API and MCP included
(`GET /datasets/{id}/views/{view}/data`, `get_dataset_view_data`) — exact numbers live on Responses and in the
export. The dataset page previews a computed view at `editor_data_view` (plain table / numbers; drawing is #704).
**Saved Responses views (`data/responses_views.py`)**: the Responses table's parameters (`required`, `q`,
`sort`/`dir`, `cf_<column>`, version) saved as a `responses` view of the survey's responses dataset, question
columns re-keyed `cf_<row id>` → `q:<code>` because publishing replaces the rows. Opening is
`…/analytics/?view=<id>#responses`: the FIRST table request carries `view=<id>` and `analytics_table` expands it
into its own parameters, so the rendered `#table-state-form` holds the filter — no second apply path in JS.
Choice filters keep the option LABELS the table matches by. Not saved: timeline brush, hidden rows, selection,
column visibility, trash. Save/delete need the editor role (`analytics_view_save`, `analytics_view_delete`).
**Tags (change `data-tags`, #673)**: `data.models.Tag(organization, name, slug)` with `datasets` and `surveys`
(canonical) relations declared on the tag — a module that takes tags adds a relation there, never a column.
`data.tags.set_tags(org, obj, names)` is the ONE writer (dataset page, `editor_survey_tags`, REST
`PUT /api/v1/surveys/{uuid}/tags`, MCP `set_survey_tags`): trimmed, ≤10, ≤40 chars, matched by slug, orphans
deleted. Filters are `?tag=<slug>` on the catalogue and the dashboard; `out.survey` carries `tags`;
`api.v1.surveys.tag_filter` serves REST and MCP `list_surveys(tag)`.
**Data in the API and MCP (change `data-api`, #674)**: `data/services.py` is the ONE write path of the
Data module (details, access, fields, tags, views, uploads, versions, delete, survey links) taking an
`Actor`; the dataset page, `api/v1/datasets.py` (`/datasets…`, `/dataset-jobs/…`,
`/surveys/{uuid}/datasets`) and `mcp/tools/data.py` all call it, and `DataRefused` maps to 422/409. Scopes
are `surveys:read` / `surveys:write`; visibility `services.dataset_row`, edit `services.can_edit`, linking
the survey owner role, Pro gate on the dataset's workspace. Raw features exist only for layer datasets
(private fields already out of the cache); collected answers leave as grid views. MCP takes files as
`content` or `content_base64` (≤ `MCP_IMPORT_MAX_BYTES`). The import writes the dataset row BEFORE
`rebuild_layer` — the rebuild reads the dictionary to drop private columns.

**Session scope (`data.scope`, change `data-scope`, Data epic #676)**: which sessions a surface
counts is ONE builder, `data.scope.SessionScope(survey_ids, include_deleted=, include_moderated=,
nonempty=, completed_headers=, external_only=)` — `.sessions()`, `.ids()`, `.q(prefix)` (related rows
of those surveys) and `.related_q(prefix)` (related rows of an already-narrowed query). No switch =
clean: not trashed, not `on_hold`, not `not_approved`. The owner's ADR-001 §6 decisions (2026-11-14) are
the surfaces' switches: `/r/` and Site results blocks use `SessionScope.public(survey)` (clean +
non-empty, so they count what Responses counts); the export keeps moderated and trashed sessions only
with `include_all` (on-hold included), and the API/MCP response scope follows the export; Responses
keeps moderated sessions (`include_moderated=True`) and names them in the headline
(`_moderated_sessions_line.html`). **Never filter `is_deleted` / `validation_status` / emptiness by
hand outside `data/`**: `SessionFilterGuardTest` (`test_session_scope.py`) fails on a new copy, and its
allow-list (single-session lookups, staff dashboards, the model) may only shrink. `data/` is a plain
package until the dataset registry (#667) makes it an app.

**Required questions unanswered / completed (`survey/required_state.py`, change
`responses-required-unanswered`, #691)**: ONE definition — a session's missing required questions
are the required top-level questions of ITS version that the visibility engine shows it (operator
surface for paper/operator sessions, respondent surface otherwise; `html`/`image` never; geo needs
`min_features`, `layer_objects` needs `min_objects` distinct objects; a blank row does not count).
*Completed* = not empty AND nothing missing — `analytics.completed_session_filter(qs)` =
`nonempty_sessions(qs).filter(required_complete=True)`, read by the Overview, the trend, the table's
Complete / Required unanswered chips (`?required=complete|missing`), the dashboard cards, the export's
`completed_only`, the REST summary and MCP (`SessionScope(completed=True)`). Reaching the last section
or the thanks page is NOT part of it. The result is STORED on the session (`required_missing` codes in
survey order, `required_complete`; both defaults agree) because counts run over thousands of sessions:
`required_state.refresh(session)` after every write of answers (`save_section_answers` — every answer
surface, forward and Back —, inline edit, paper supersede, ZIP import), and
`schedule_survey_refresh(header_id)` (on commit; inline up to `SYNC_LIMIT` non-empty sessions, else the
`recompute_required_state` task with an inline fallback) when an in-place edit changes the required set
(`services/questions.py::_required_set_changed`, create of a required question, delete). **A new path
that writes answers or changes what is required must call one of the two.** Publishing needs nothing:
old sessions move with their structure. The marker is quiet (`_required_unanswered_mark.html`: grey,
no count, tooltip names the questions); the one per-answer note left is crossed polygon edges
(`SurveyAnalyticsService.crossed_shapes`). The old Issues engine (duplicate by User-Agent, fast,
last-section "incomplete", outliers) and the survey validation-settings dialog are gone on purpose —
creators deleted real answers because of them; do not bring per-session "issues" back.
`SurveyHeader.validation_settings` is an unused column. Number questions' `min_value`/`max_value`
are enforced (input `min`/`max`, `views.number_value` drops an out-of-range POST; spec
`number-question-bounds`).

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

**The report as a story (change `reports-story`, #704 part 1; owner direction 2026-11-16)**: Reports is a
STORYTELLING module and v1 is the LINEAR story — one column, text with charts, maps and quotes between the
paragraphs. Acceptance rule: every report made by hand can be opened by its customer in Reports and edited
there. So: (1) **story blocks** — `heading`, `text` (rich, `reports.story.clean_html` = `coerce_creator_html`),
`image`, `numbers` and `quotes` (`ReportBlock.config = {"items": […]}`, typed by the author: typed numbers are
ALLOWED; `reports.story.clean_config` is the one cleaner, the editor posts them as lines `value | label` /
`quote | source`); `ReportBlock.width` `full | half`, two consecutive halves share a row
(`render.story_rows`) — never a container block. (2) **One editor, two ways in**: every view in
`reports/editor_views.py` is written once and exported twice, `on_survey(view)` (the survey's Public results
tab, URL names `editor_public_results_*`) and `on_report(view)` (`/editor/reports/<uuid>/…`, names
`editor_report*`); both set `request.report` / `request.survey` (None for a blank or imported report) and
the template takes EVERY url from the `u` dict (`_urls(request)`) — never `{% url … survey.uuid %}` there.
`may_edit_report` = workspace editor + editor on the home survey when there is one; strangers get 404.
(3) **The report file** (`reports/files.py`): a ZIP with `report.json` (`format: 1`) + `images/`; question
blocks by survey uuid + question CODE, re-bound on import (`data.questions.question_of`) or left out with a
message; an import is always unpublished and `workspace`-only, text re-sanitised. Hand-made HTML reports are
turned into that file by the ops repo's `scripts/report_html_to_file.py` — customers' reports never enter this
repo. (4) The page (`public_results.html`) renders `rows`; a text payload carries `html`, and a snapshot frozen
before this change has only `body`, which the template ESCAPES. A report without a survey has no comment
threads (threads hang on a survey) and no "N responses".
**Live blocks (change `reports-live-blocks`, #704 part 2)**: `crosstab` and `engagement` blocks point at a
`DatasetView` of that kind (`ReportBlock.view`, `VIEW_BLOCK_TYPES`); `services.add_view_block` MAKES the view in
Data (`data.services.create_view`, or reuses an identical one) — Data's refusals are the block's. The payload is
`dataviews.result(view, lang, k=<the REPORT's K>)` plus presentation only (`render._view_payload`): no count is
produced in `reports/`. **A map block may show the marks themselves** — `config = {"marks": true}`, a per-block
switch, off by default (owner decision 2026-11-16: the survey owner's choice and responsibility); the payload is
then `data_type: "marks"`, geometry only. That exception is a report block's ALONE: Site results blocks, grid /
coverage / density views, the Data API and MCP keep the grid (`public-aggregates`). **Live numbers**:
`reports/tokens.py` fills `{responses}` `{opened}` `{finished}` `{marks:CODE}` `{respondents:CODE}` in Text
blocks, key numbers and the opening paragraph from the HOME survey, masked with the report's K; a token that
cannot be filled stays as written; a frozen snapshot stores the filled text (and `intro_body`). The report file
carries all of it (`crosstab` by survey + two codes, `engagement` by survey, a map's `marks`).
**Starting a report (change `reports-start`, #705)**: `/editor/reports/start/` (`reports.views.report_start`,
`reports/start.html`) — one click on a card does its action (each card is the submit button of its own form;
do not add a "choose, then confirm" step). `reports/drafting.py::build_draft(actor, survey, template)` builds a
NEW report by RULES, never a model and never into the survey's first report: key numbers and the engagement
block first, then one block per top-level question that has answers in clean sessions, in respondent order,
section titles as headings; four arrangements (`TEMPLATES`: `summary`, `council`, `update`, `yousaid`) are
small builder functions over `_Draft`. **Hidden instead of placeholder**: prompts ("Write what this part…") and
candidate quotes from free-text questions (≤ 8 recent answers of 30–320 chars) are real blocks with
`is_hidden=True`, so publishing an unfinished draft shows none of them and a quote reaches the page only after
the author un-hides it. `copy_report` = the report file's export + import in memory (a copy cannot keep what an
export would lose). Entry links: Reports list, Responses of a published survey, the responses dataset.
Events `report_entry_seen` / `report_created` carry ids and choice names only. `Report.template` records the
arrangement.
**Before you publish (change `reports-review`, #706)**: `reports/checks.py::run(report)` is the ONE list —
`privacy` (every VISIBLE quote written out, every map with marks, K = 1) and `other` (a block the renderer
returns None for → "Delete the block"; a map without a description; no title; hidden blocks counted). A new
check is a few lines there. `services.set_published(actor, report, publish, ack, visibility, mode)` refuses
`ack_required` when `checks.needs_ack` (a visible quote or a map of marks) and the author did not tick the
box — nothing else blocks, K = 1 is only listed. Every "Publish" button opens the dialog (`prOpenPublish()`,
body `editor/partials/pr_checks.html` fetched by HTMX from the `checks` route each time), which also posts
`visibility` and `mode` (live | frozen). A map block's `content` is its description: shown under the map and
`role="img"` + `aria-label` on the container. The preview pane has phone / computer widths. Comment threads
exist on blocks of a survey's report only (a thread belongs to a survey).
**The PDF of a report (change `reports-pdf`, #707)**: `reports/pdf.py::build_pdf(report, base_url)` lays out
the PAGE'S OWN payload (`render.build_context` → `rows`) on A4 with reportlab — NOT a headless browser — so a
number in the PDF is the number on the page and nothing is counted there; a new block type needs a branch in
`pdf._block` as it does in the template. Maps = `survey.print.static_map` basemap of the block's extent with
cells / marks painted by Pillow (no token or a Mapbox error → plain ground). Every block is `KeepTogether` and a
heading is folded into the block after it. **Never rendered in a web request**: `services.request_pdf` creates
a `ReportPdf` row (private media tier, `report_pdfs/<uuid>.pdf`) and enqueues `reports.tasks.render_report_pdf`,
which claims the row (`queued → running`), so a redelivered message does nothing; the editor's button polls
`editor_report_pdf`. `stamp`: a FROZEN report has one PDF per snapshot, reused and linked from its page
(`/r/<slug>/pdf/`, the page's own visibility guard); a LIVE report gets a new rendering per request and no public
link. No PDF is made at freezing time. Tests patch `survey.print.static_map.fetch_basemap` so no test calls Mapbox.
**A report outside its page (change `reports-embed`, #708)**: embedding REUSES the survey embed mechanism —
`reports.embed.mark(request, report)` sets `request.survey_frame_ancestors` (so `SurveyEmbedMiddleware` applies
`frame-ancestors` from `Report.embed_allowed_hosts`, empty = `*`), the page in `?embed=1` posts the same
`{mapsurvey: "height"}` message and the same `/embed.js` grows the iframe. Only a published `public` /
`unlisted` report is framable; `workspace` keeps `SAMEORIGIN`. One block has its own page,
`/r/<slug>/block/<id>/` (the report's template with ONE row, `single=True`); `/oembed/` answers report and block
links. **CSV and PNG are made from the block's PAYLOAD, never from answers** — `reports/tables.py::rows_of`,
`reports/pictures.py::block_png` (Pillow: bars, a table, `pdf.map_image`) — so a group the page hides is "<K" in
the CSV and its value is not in the file. Public CSV at `/r/<slug>/block/<id>/data.csv`; an editor's CSV / PNG at
`editor_report_block_file`; all blocks as one ZIP = the PDF's worker job with `ReportPdf.kind = 'zip'`
(`reports.tasks.build_zip`). A "Report" block for Sites is not built (a Sites block kind; follow-up).
**The next round (change `reports-reuse`, #711)**: `drafting.copy_report(actor, report, onto=None)` is still the
report file's round trip; `onto` (a survey) goes to `files.import_report(onto=)`, which makes it the home survey
and resolves EVERY data block's survey to it, matching by question code. A block that finds no question is,
with `onto`, kept as a HIDDEN text block naming it (`unmatched()` in `import_report`) and listed in
`copy.copy_notes` (the start page flashes them); a plain import keeps leaving it out with a note. Never drop a
block without a note. `compare` is a block type of its own (not in `QUESTION_BLOCK_TYPES`): `dataset` +
`question_code` as a chart's, `config = {"other": "<survey uuid>"}`; `services.comparable(question, other)` is
the ONE rule for "can be compared" (same code, both chart types, both numeric or both not) used at add time and
at render time; `ReportService._compare_payload` joins two `_choice_data` / `_number_data` aggregations by
option code — shares of the people who answered, masked per round, no share for a masked cell or a round under
K. The page, the PDF and the CSV draw the same `rows`. Event `report_reused` (ids and counts).
**Readers, tags, API and MCP for reports (change `reports-usage-api`, #710)**: `reports/usage.py` counts, per
report and DAY, `view` / `embed` (`?embed=1`, a block's page included) / `pdf` in `ReportUsage` — one row per
day and kind, no visitor stored, a signed-in member of the report's workspace not counted, a failed count never
breaks the page; `usage.summary` feeds the editor's Readers card and the API. Do not add per-visitor rows or a
third-party script to `/r/`. A report takes workspace tags through the Data module's `Tag.reports` and
`data.tags.set_tags` (`services.update_settings(tags=)`). **API and MCP write blocks from plain values through
`reports/blocks.py`** (`add` / `change` / `describe`): a spec dict → the SAME `reports.services` calls the
editor makes; what a block looks like outside the database is `reports.files.entry_of` — the report file and
the API share it, so a new block type is described once. `api/v1/reports.py` holds the routes AND the functions
the MCP tools (`mcp/tools/reports.py`) call (`report_for`, `create`, `save_settings`, `publish`, …); scopes are
the surveys' (`publish` → `surveys:publish`, delete → `surveys:delete`); two gates: `require_pro_api` on the
workspace and, on writes, `reports.gate.use`. REST publishes a report with quotes or marks only with
`confirm: true` (409 `conflict`); MCP `publish_report` / `delete_report` answer `confirmation_required`. Image
blocks are editor-only (no upload in the API).
**Reports is Pro (change `reports-pro`, #709; owner decision 2026-11-16)**: feature `reports` in
`billing/features.py`, in the trial UNCAPPED (the trial's limit is its 90 days). `reports/gate.py` is the one
place: `covered(org)` = plan or a live trial (`Entitlements.covers`, NOT `may` — a report made under the trial
stays alive until the trial ends); `use(org, user)` lets a WRITE through, starting the workspace's trial when it
never had one; `freeze_if_lapsed(report)` freezes a published live report of an uncovered workspace. **Writes are
gated, reading never is**: every POST of the report editor passes `_gated` in the `on_survey` / `on_report`
wrappers, plus `report_create`, `report_start` and `report_import`; the refusal is `editor_views.paywall`
(`billing.gates.feature_required`, or 403 JSON `pro_required` for autosave) and emits `report_paywall_shown`.
The editor's GET, export, PDF and ZIP work on any plan (banner `reports_locked`). **The public routes never
answer 404 or an upgrade page for the plan**: `report_page` and `_guard` (block page, CSV) call
`freeze_if_lapsed` first, so a lapsed or never-Pro workspace's report is its snapshot at the same address.
`manage.py freeze_reports_without_pro [--dry-run]` lists and freezes them all (ship day). The survey's first
report is still drafted for free by `scaffold_report` — the product drafting, not a member writing. A new
write endpoint for reports must go through the wrappers or call `gate.use`.
**Reports (`reports/`, change `reports-object`, #703; epic #712)**: what was the public results
page is a **report** — `reports.models.Report` (a workspace object at `/r/<slug>/`, `survey` = its
HOME survey, nullable and not unique) with ordered `ReportBlock`s. A question block names a
**dataset of the Data module and the question's code**, never a question row (`publish_draft()`
replaces rows): a map block reads the `answers` dataset of (canonical survey, code), chart / objects
/ budget blocks the survey's `responses` dataset. `block.question` is a cached property
(`reports.sources.question_for`; lists go through `attach_questions`), and
`ReportBlock.objects.create(question=q)` fills dataset and code. So one report may read several
surveys, and `ReportService` scopes sessions PER BLOCK (`_scope_of(question)`), not per report.
Rendering is `reports/render.py` (`ReportService`, `render_data`, `freeze_report` /
`unfreeze_report`, `scaffold_report`, `report_for_survey`, `k_for_survey`); every write is
`reports/services.py` with an `Actor`. `SurveyHeader.report` (the survey's oldest report) is what
the Public results tab, the thanks button, Share and the dashboard pill read — never
`Report.objects.get(survey=…)`, a survey may be home to several. The editor is the report builder
below (`reports/editor_views.py`; URL names `editor_public_results_*` through a survey,
`editor_report*` by the report). Aggregates run over CLEAN
sessions only (not deleted, excludes `not_approved`/`on_hold`) across the canonical survey + all
versions. Privacy: k-anonymity masks buckets `<K` (default 3); geo popups expose only
creator-selected `geo_label_fields`; individual free-text answers are not published (hand-picked
quotes arrive with #704). Hybrid `live` (60s cache) vs `frozen` (snapshot) mode. Visibility
`public` (indexed, in sitemap), `unlisted` (noindex) or `workspace` (signed-in members of the
workspace only: anonymous → login, others → 404). "Used by": `data.links.report_places`; a
`DatasetView` a block shows cannot be deleted (`view` is `RESTRICT`), a dataset that disappears
leaves the block empty (`SET_NULL`). The Reports list is `/editor/reports/`. Report config is
intentionally NOT included in survey ZIP export/import. Migration `reports/0002` copied the old
pages WITH their ids (comment anchors, snapshots, `?block=` links).

**Report builder (change `reports-canvas-editor`, #731)**: the report editor is the Sites canvas
builder for a report — `reports/builder.html` runs on the SAME script and stylesheet as Sites
(`js/site_builder.js`, `css/site_builder.css`, every `lb-` hook) plus `js/report_builder.js` /
`css/report_builder.css` for what only a report has (publish dialog, PDF job, half-width pairs, the
library's two forms). Do not fork a second builder script; a change to `site_builder.js` must keep
both pages working. Left: outline; centre: the report as readers see it, written in place
(`reports/editor/_canvas_block.html`, `_hero.html`); right: ONE context panel — the selected block's
form (`_block_panel.html`, the WHOLE block: what is written on the canvas travels in its hidden
fields) or the report's settings (`_page_panel.html`). `reports/canvas.py` builds one record per
block, hidden and empty ones included, with the `note` saying why readers do not see it; nothing is
cached there. A save posted with `autosave=1` is answered with fragments (`block`, `outline`,
`panel`; settings: `title`, `hero`) computed for THAT block only (`_block_fragments`,
`_shell_context`) — never rebuild the whole canvas in an autosave answer. Key numbers and quotes
post parallel lists behind `rows=1`; the `items` textarea dialect stays for the API-less callers and
tests. Readers' markup is ONE partial, `reports/_block.html`, and ONE stylesheet,
`css/report_public.css`, every rule under `.rp` with the row class `rp-row` (the canvas lives under
Bootstrap, whose `.row` is a flex row): a look changed there changes `/r/`, embeds and the canvas.
A field that shows a live number (`{responses}` in a key number or the opening) carries the token
in `data-raw` and `plainValue()` returns that until the author clicks into it — never save
`innerText` of such a field. A question block's empty title means "the question's name", shown as
the placeholder (`rb-default-title`); `?block=<id>` selects a block (publish checks, comment mail).
Blocks are added from the library (`_library.html`): `block_type`, or `question_id` for a chart /
map, with `after` (`top` | block id) — `_place` renumbers through `reorder_blocks`. A picture block
may be created empty. The builder extends `editor_base.html` (Sites extends `base.html`): through a
survey it is that survey's Public results tab and keeps the survey's title, tab strip and publishing
widget above it — tests hold every survey page to that. The old tab's own mobile status line and
Structure / Edit / Preview bar are gone; on a narrow screen the panel sits under the canvas, as in Sites.
Both builders' side panels are resized by dragging their inner edge (`initPanelResize` in
`site_builder.js`; widths are the `--lb-rail-w` / `--lb-panel-w` variables on `.lb-work`, kept in
`localStorage['msBuilderPanels']`, double click = default) — a new column rule must keep those variables.
A report is deleted from its row in the Reports list or from its settings (`reports/_delete_confirm.html`
holds the dialog's wording for both; `editor_report_delete` takes the POST only). "New report" creates a
blank report in one click; the start page offers the blank card only — the four arrangements and "Copy an
earlier report" are off the page since 2026-11-18 (owner: get the blank report right first), while the view
still takes `kind=draft|copy`.

**One confirmation dialog (change `one-confirm-dialog`)**: every "are you sure?" a creator sees is
`partials/_app_dialog.html` (`#editorDialog`), included by `base.html` and `editor_base.html` and driven
by `js/editor_dialog.js`. From script: `Dialog.confirm(text, {title, note, okLabel, danger})` /
`Dialog.alert()`. From markup: a form with `data-confirm="<title>"` and optional `data-confirm-body`,
`-note`, `-action`, `-tone="primary"` (an action that destroys nothing; default is the red button), or
`hx-confirm`. Never add a browser `confirm()`, a second confirm modal or a confirmation PAGE — there were
five kinds before this change. A modal with choices of its own (group delete, the dashboard's Trash /
Purge) stays a modal of its own.

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

**Blog and public changelog (change `public-blog-and-changelog`, #647)**: `/blog/` is ONE feed of
published customer stories (`Story` rows, still at `/stories/<slug>/`) and **articles**, which are
FILES — `survey/blog/<YYYY-MM-DD>-<slug>.html`, a `---` header (`title`, `kind: feature|idea`,
`summary`; optional `cover`/`cover_alt`, `author`, `topics`, `changelog`, `updated`, `draft`) and an
HTML body whose pictures are `{static:img/blog/<slug>/…}` tokens. An article ships in the PR of the
feature it describes, so a merge publishes it — never put articles on `Story` (that path needs a
production `seed_story` and the customer's consent); format and rules in `survey/blog/README.md`,
loader `survey/blog.py` (`feed_items`, `article_map`), views `survey/blog_views.py`. Articles are for
the MOST important changes and are not a copy of the changelog entry; the entry ids named in an
article's `changelog` header get "Read the article" on `/changelog/` and `/editor/whats-new/`.
`/changelog/` renders the same `survey/changelog/` entries publicly (anchors = entry ids, no editor
links, no hero chips). RSS: `/blog/feed.xml`, `/changelog/feed.xml` (absolute links from
`public_base_url`). `draft: true` = staff-only + `noindex`, off the feed, RSS and sitemap.
`BlogArticlesTest.test_shipped_articles_load` fails CI on a malformed file.

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

**Registration abuse prevention**: `/accounts/register/` is served by `AbuseProtectedRegistrationView` (subclass of `AsyncEmailRegistrationView`). Two defenses run in order: honeypot field `website` (silent fake-success redirect), per-IP rate limit (`django-ratelimit`, fail-open on Redis outage). Cloudflare Turnstile was removed (#490) after it had been off in production; do not bring a CAPTCHA back without the owner — what an unconfirmed account can do is bounded by the grace period below. Helpers in `survey/abuse.py`. Audit log in `AbuseEvent` model. Real client IP via `survey.middleware.CloudflareIPMiddleware` reading `CF-Connecting-IP` only when `CLOUDFLARE_TRUSTED=True`.

**Sign-in grace period (change `login-grace-period`, #487)**: registration creates the account
ACTIVE and signs it in; `EmailVerification` (one row per account, no row = confirmed) records the
email confirmation, and `User.is_active=False` means ONLY a ban (`confirm_phishing`). The one rule
is `survey/email_verification.py` (`is_verified`, `grace_deadline` = `date_joined` +
`SIGN_IN_GRACE_HOURS` (24), `can_sign_in`, `awaits_confirmation`, `confirmed_q`, `send_link`):
never read `is_active` as "activated" and never compute the deadline elsewhere. Unconfirmed
accounts build freely for 24 h, but `services/publishing` refuses to publish (`EmailUnconfirmed`
→ editor 403 + dialog, REST/MCP `403 email_unconfirmed`) and `org_send_invitation` refuses to
invite; email-matched invitations are accepted on CONFIRMATION (`user_activated`), not at
registration. Past the deadline the backend refuses the password, `SignInForm` names the reason
to whoever typed the CORRECT password and sends a link (per-address daily cap shared by every
send), and `GracePeriodMiddleware` ends a grace session at its next request. There is no standing
confirm-email banner (removed in change `onboarding-friction`, #638 — it pulled new creators off
onboarding): `editor/partials/_confirm_email_banner.html` (both bases) now holds only the
"Confirm your email to publish" dialog and its resend script; do not bring a banner back. Newsletter and funnel
"activated" use `confirmed_q()`. After a deploy that touches accounts, run
`manage.py sync_email_verification` (idempotent) for rows the old instance created.

**Workspace invitations (change `invite-landing-journey`, #512)**: `survey/invitations.py` is the ONE
place an `Invitation` is accepted — `accept()` writes the membership (an existing member keeps their
role), `accepted_at`, the active workspace and a one-shot "just joined" mark in the session, and
emits `invitation_accepted` (org id, role, `surface` ∈ `link|register|sign_in|confirm`). The signed-in
accept view, `ActiveOrgMiddleware` (token parked by the landing page), the registration receiver and
the confirmation-time address match (`join_by_address`, rule of #487 unchanged) all call it; never
write `Membership` from an invitation elsewhere. **A registration that carries an acceptable
invitation gets NO personal workspace** (owner decision 2026-10-31): `create_personal_org_on_registration`
asks `accept_pending()` first and returns when it joined; a dead token falls through to the personal
workspace so no account is left without one. The landing page's two actions carry the token
(`/accounts/register/?invite=<token>`, `/accounts/login/?next=<accept URL>`), and the register page
pre-fills the invited address. The dashboard pops the mark once (`take_joined`): that render shows the
"You've joined" banner and never redirects to the start page; `editor_sees_none` is the editor's empty
state in a workspace that has surveys. `DirectActivationView.post` signs in BEFORE sending
`user_activated`, because `login()` flushes a session another account held.

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
