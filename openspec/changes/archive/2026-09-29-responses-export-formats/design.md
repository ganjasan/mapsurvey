## Context

`download_data` (`survey/views.py:1428`) builds a ZIP in a `BytesIO`: `_export_survey_data` writes
one GeoJSON FeatureCollection per geo question (sub-question answers as properties, session
metadata, shared-map verdicts), `_export_object_answers` writes `objects_<code>.csv` per
"Objects on the map" question plus the layer's results GeoJSON, then a CSV of one row per session
holding every non-geo answer, then the respondent files under `files/<session_id>/`. Two GET
parameters exist: `version` (resolved by `_get_version_surveys`, shared semantics with analytics
since `version-filter-parity`) and `include_all=1` (trashed and `not_approved` sessions back in).
Cell formatting is centralised in `_answer_cell` with the explicit type classification introduced
by `export-data-integrity`; the tests pin values, not just counts.

Three UI entry points reach the view: the "Download" button on both Responses dashboards
(`?version=<current>`), the survey card "..." menu on the editor dashboard (`Download Clean Data` /
`Download All (incl. excluded)` groups with per-version links when archived versions exist), and
the survey card link named by `survey-cards`. The same "..." menu has an "Export" group that
serves `export_survey` — the survey.json backup that ZIP import consumes. Creators confuse the two.

Constraints:
- Python 3.9 / Django 4.2 on master and production (`python312-django52-upgrade` is not merged).
- Memory (`layer-memory-diet`): a gunicorn worker keeps the RSS of its largest request. The
  export must not add a second copy of the data in memory on top of what the legacy path holds.
- `gdal-bin` is in the `Dockerfile` for GeoDjango. The base image `python:3.9-slim` currently
  resolves `gdal-bin` 3.10 (checked 2026-09-29); the dev machine has 3.8. Both ship the `GPKG`,
  `ESRI Shapefile`, `LIBKML`/`KML`, `CSV` and `XLSX` vector drivers with write support. No
  `osgeo` Python bindings are installed in the venv and none are wanted.
- `TIME_ZONE='UTC'`, `USE_TZ=True`; the Responses page renders session times in UTC.
- Deadline: City of Olney switches to year-round reporting on 2026-10-03 and needs the flat
  Excel sheet before then. lead-119's GIS formats have waited since March.

## Goals / Non-Goals

**Goals:**
- A creator without a GIS gets a file that opens in Excel and answers "what was observed where"
  one row per observation.
- A creator with a GIS gets GeoPackage (default recommendation), Shapefile or KML without
  converting GeoJSON themselves.
- One dialog states the choices (format, scope, filters) and produces a copyable URL.
- The survey backup and the data export are visibly different things.
- The legacy ZIP is unchanged for anyone holding an old link or a script.
- No new memory ceiling; no new service.

**Non-Goals:**
- CRS selection (everything leaves as WGS84 / CRS84; a GIS reprojects).
- Field selection, spatial extent, encoding choice — the QGIS "Save As" knobs a clerk never
  touches. The dialog has three fields and three checkboxes.
- Scheduled or emailed exports, an export job/queue (the current synchronous response is fine at
  today's sizes; see Risks for the trigger that would change this).
- A per-answer observation timestamp: only `SurveySession.start_datetime` exists (backlog
  `bug-session-end-datetime-never-set` is separate). The observations table says "session start".
- Changing what the public results page or the ZIP survey backup contain.
- The Objects editor's own GeoJSON/CSV import formats.

## Decisions

### D1. One collector, several writers, in `survey/export.py`

The export code leaves `views.py` for a module with two halves:

- `collect(survey, version_surveys, excluded_session_ids, completed_only)` walks the database ONCE
  and returns an `ExportBundle`: per geo question a FeatureCollection dict plus, per feature, the
  GEOS geometry it came from; the per-session rows; the per-session metadata; the object-answer
  records and results GeoJSON; the file answers. It is the existing `_export_survey_data` /
  `_export_object_answers` logic with `zip.writestr` replaced by appending to the bundle.
- Writers take a bundle and a target: `write_legacy_zip` (byte-identical content to today),
  `write_xlsx`, `write_csv_zip`, `write_ogr(driver)`.

`_answer_cell`, the classification sets and `_upload_archive_path` move with it; `views.py` keeps
`from .export import _answer_cell, EXPORT_VALUE_TYPES, ...` so tests importing from `views` keep
working. Alternative considered: a second, parallel code path for the new formats reading the
database again. Rejected: two paths drift (this is how analytics and export disagreed on `version`),
and the flat table must agree with the GeoJSON properties by construction.

### D2. The flat observations table is derived from the same features

One row per feature of every geo question in the family, columns in this order:

`session_id`, `session_start_utc`, `session_language`, `validation_status`, `version`, `section`,
`question`, `question_code`, `geometry_type`, `lat`, `lon`, `wkt`, then the sub-question columns,
then the shared-map columns (`mark_key`, `votes_up`, `votes_down`, `comments`) when any question in
the bundle has them.

- `lat`/`lon` are the point's coordinates; for a line or polygon the centroid (GEOS `centroid`),
  because a clerk sorting by place wants one number pair per row. `wkt` carries the full geometry
  for every row so nothing is lost; for a point it is `POINT (lon lat)`.
- Sub-question columns are keyed by sub-question NAME and shared across questions: Olney's
  `Quantity` on the white-squirrel question and `Quantity` on the fox-squirrel question are one
  column, and `question` says which animal. Alternative: `question.sub` prefixed columns.
  Rejected: it turns a 6-column sheet into 20 sparse ones and the customer's example table is the
  merged shape. Two sub-questions with the same name on the same question cannot exist (unique
  code per section), so a merge never overwrites within a row.
- Ranking answers expand to one column per item as `_answer_cell` already returns; write-in
  "Other" columns come through the same dict.
- Object answers (`layer_objects`) are NOT rows here: they describe a creator's object, not a
  placed feature. They keep their own sheet (D3).

### D3. Excel workbook layout

Sheets, in order: `observations` (D2), `responses` (one row per session, the legacy CSV columns
with `datetime` renamed `session_start_utc`), `sessions` (`session_id`, `session_start_utc`,
`session_end_utc`, `language`, `validation_status`, `opened_by_kind`, `version`, `tags`, `notes`),
and `objects_<code>` per "Objects on the map" question when the survey has any.

- Written with `openpyxl` in **write-only mode** to a `NamedTemporaryFile`, streamed back with
  `FileResponse`. Write-only mode keeps one row in memory at a time; the bundle itself is what the
  legacy ZIP already holds, so peak RSS does not move.
- Datetimes are written as naive UTC `datetime` objects (Excel has no zone; the column header
  carries `_utc`) with number format `yyyy-mm-dd hh:mm`. Numbers are numbers; `lat`/`lon` are
  floats with `0.000000` format. Everything else is text. Header row bold and frozen; column
  widths set from the header length clamped to 12–40 characters (write-only mode allows
  `column_dimensions` before rows are appended).
- Sheet names are sanitised to Excel's 31-character, no `[]:*?/\` rule.
- Alternative: GDAL's own XLSX driver via `ogr2ogr`. Rejected: no header styling, no widths, and
  one layer per sheet means no `responses`/`sessions` sheets without a second code path.
- Alternative: `xlsxwriter`. Rejected: `openpyxl` is the more common dependency and write-only
  mode is enough; nothing here needs charts.

### D4. GIS formats through `ogr2ogr` on temp files

`write_ogr(bundle, driver)` writes each FeatureCollection to `<tmp>/<name>.geojson`, lists them
all in ONE OGR VRT (`<OGRVRTLayer>` per layer with its `GeometryType` and `LayerSRS`, so an empty
layer still gets its geometry type) and runs `ogr2ogr` ONCE per export on that VRT, which yields a
multi-layer GeoPackage or KML, or a directory of shapefiles:

| Format | Driver | Output | Layer mapping |
|---|---|---|---|
| `gpkg` | `GPKG` | one `<survey>.gpkg` | one layer per geo question, plus one layer per layer-objects results GeoJSON |
| `shp` | `ESRI Shapefile` | ZIP of `<name>.shp/.shx/.dbf/.prj/.cpg` per question | `-lco ENCODING=UTF-8`; GDAL launders field names to 10 chars and reports the mapping on stderr, which is logged |
| `kml` | `LIBKML` (falls back to `KML`) | one `<survey>.kml` | one container per question — a nested `Document` under LIBKML, a `Folder` under KML; `-dsco NAME=<survey>` for LIBKML |

- Layer/file names are `_sanitize_filename(question.name)` deduplicated with a numeric suffix
  (two questions may share a name across sections).
- `subprocess.run([...], check=True, capture_output=True, timeout=120)`. A non-zero exit or a
  timeout raises `ExportError`; the view answers 500 and PostHog error tracking gets the stderr
  in the message. The legacy ZIP is unaffected because it never shells out.
- Availability: `export.OGR_AVAILABLE = shutil.which('ogr2ogr') is not None`, evaluated at import.
  When False the dialog does not offer `gpkg`/`shp`/`kml` and the view answers 400 for them.
  This is what keeps a dev machine without GDAL working; production always has it.
- Alternatives: `fiona`/`geopandas` (heavy wheels, their own GDAL, memory), `pyogrio` (same),
  GeoDjango's `django.contrib.gis.gdal` (read-side `DataSource` only; no writer API). Shelling out
  to the binary that is already installed costs nothing and isolates the conversion from the
  worker's memory.
- Field names longer than 10 characters in Shapefile are the customer's sub-question names; the
  dialog's Shapefile description says they are shortened and recommends GeoPackage. This is why
  GeoPackage is listed first among GIS formats.

### D5. The URL contract of `download_data`

`GET /surveys/<slug>/download` gains:

| Param | Values | Default | Meaning |
|---|---|---|---|
| `format` | `zip` `xlsx` `csv` `gpkg` `shp` `kml` | `zip` | `zip` is the legacy GeoJSON+CSV archive, unchanged |
| `version` | existing | existing | unchanged |
| `include_all` | `1` | off | unchanged |
| `completed_only` | `1` | off | only sessions that answered their version's last section (D6) |
| `files` | `1` | off | include respondent uploads; forces a ZIP container for single-file formats |

Container rule: `zip` and `shp` are always a ZIP; `xlsx`, `gpkg`, `kml` are a single file unless
`files=1`, in which case the single file sits at the ZIP root next to `files/`; `csv` is a ZIP of
`observations.csv`, `responses.csv`, `sessions.csv` and the `objects_*.csv` files (`files/` when
`files=1`). CSVs are UTF-8 with BOM so Excel on Windows reads them as UTF-8; the legacy `zip`
keeps its BOM-less pandas CSV so existing scripts see no change. An unknown `format` answers 400.

`data_exported` is emitted with `format=<chosen>`; a legacy link with no `format` still says
`zip`.

### D6. "Completed" has one definition

`analytics.py` already defines completion for the overview as "the session has an answer to a
question of its version's last section" (`_completed_filter_qs`). That logic moves to a module-level
`completed_session_filter(qs, headers)` in `survey/analytics.py`, used by
`PerformanceAnalyticsService` and by the export's excluded-id computation. Alternative:
`end_datetime IS NOT NULL` (set by `mark_completed` on the thanks page since `user-last-activity-
tracking`). Rejected for now: it is unset on every session before that change shipped and on
sessions whose respondent closed the tab on the last section, so the two surfaces would disagree
on old surveys. When the counts converge the definition can switch in one place.

### D7. The dialog is one partial, hosted twice

`editor/partials/_export_modal.html` + `survey/assets/js/export_dialog.js`. The partial is included
once on each Responses dashboard and once on `editor.html`; it reads `data-survey-uuid`,
`data-version`, `data-has-files`, `data-version-choices` from the button that opened it, the way the
existing `#deleteModal` does, so the survey-card menu needs no per-card markup. Fields:

1. **Format** — radio list, each with a one-line description and the audience it serves:
   Excel (`.xlsx`) · GeoPackage (recommended for QGIS/ArcGIS) · Shapefile · GeoJSON + CSV
   (current archive) · KML · CSV. GIS rows are absent when `OGR_AVAILABLE` is False.
2. **Version** — the same choices `version_choices(survey)` gives the Responses page; preselected
   from the opener. Hidden for a single-version survey.
3. **Include excluded responses** — off. **Completed responses only** — off. **Include attached
   files** — shown only when `has_files`; off; its hint says the download becomes a ZIP.

The primary button is "Export" and navigates to the built URL (`location.href`, so the browser
shows its download UI; no fetch, no blob). The last chosen format is remembered in
`localStorage['exportFormat']` — browser-only, like every other Responses preference. The opener
buttons read "Export data" with a `fa-file-export` icon; the "..." menu group for `export_survey`
reads "Backup (survey file)" with the hint "for import into Mapsurvey, not for analysis". The
survey card's plain link (`survey-cards`) keeps pointing at the legacy ZIP and is not part of this
change.

Mobile (`MOBILE_EDITOR_NAV`): the modal is a standard Bootstrap modal and needs nothing from the
mobile nav; the toolbar button is already in the strip that the nav keeps.

### D8. Streaming and memory

`FileResponse(open(tmp, 'rb'))` with a `TemporaryDirectory` whose cleanup is deferred to
`response.close` via `FileResponse`'s `_resource_closers`. The legacy `zip` keeps its `BytesIO`
because the test-suite compares its bytes and its size is what the worker holds today. `csv`
and the ZIP containers for `files=1` write into a temp file with `ZipFile(..., 'w', ZIP_DEFLATED)`
and append uploads by streaming `storage.open()` chunks (`zip.open(name, 'w')`), which is
strictly better than the current `stored.read()` into memory.

## Risks / Trade-offs

- [ogr2ogr behaves differently between GDAL 3.8 (dev) and 3.10 (image)] → tests assert on what
  we control: layer names, feature counts, field values read back through `ogrinfo -json` /
  sqlite for GPKG; the fixture GeoJSON is tiny. `run_tests.sh` runs on the host, so a host without
  `ogr2ogr` skips those tests with a reason (`skipUnless(OGR_AVAILABLE)`).
- [The base image's Debian release moves under `python:3.9-slim`] → the memory note
  `lesson_python_slim_debian_jump` already covers it; the Dockerfile pins nothing here and the
  export depends only on drivers every GDAL since 2.x ships.
- [A large survey with many uploads and `files=1` takes long enough to hit the Render 30 s proxy
  timeout] → the legacy ZIP has the same exposure today and no report; `files` defaults off for
  the new formats, which is the opposite of today's ZIP. If a report comes, this becomes a job
  like `SurveyImportJob`, in a new change.
- [Merging sub-question columns by name hides two different questions named alike] → the
  `question` column disambiguates every row; the `responses` sheet keeps the per-question layout.
- [Moving 400 lines out of `views.py` breaks an import somewhere] → re-exports in `views.py`,
  and the six existing export test classes run before any new format is written (task order).
- [Shapefile truncates and mangles field names] → said in the dialog; GeoPackage is listed first
  and marked recommended.
- [Excel opens `lat`/`lon` with a locale comma] → they are numeric cells, not text; the comma
  trap only bites CSV, and the CSV format carries a BOM and a `.` decimal like every GIS export.
- [`completed_only` on a survey whose last section holds only display-only questions yields zero
  rows] → same as the overview's "completed" count today; the dialog hint says "answered the last
  section".

## Migration Plan

One PR from `feature/responses-export-formats` to master. Task order inside it keeps the legacy
ZIP green first (refactor, then existing tests), then adds formats; if the deadline for City of
Olney (2026-10-03) presses, the PR ships when Excel and the dialog are done and the GIS formats
follow on the same branch before merge — never as a separate change.

Rollback: revert the PR. Old links never changed (`format` absent = legacy ZIP), no migrations,
no data changes, no new env vars. `openpyxl` enters `Pipfile`/`Pipfile.lock`
(`pipenv install openpyxl` from the 3.9 venv so the lock stays on the production interpreter).

## Open Questions

- None blocking. Whether `completed` should switch to `end_datetime` once old sessions age out is
  a one-line change in `completed_session_filter` and can be decided later.
