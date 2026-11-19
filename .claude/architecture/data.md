# Data module: catalogue, uploads, links, versions, views, tags, session scope, export, ZIP import

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

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
