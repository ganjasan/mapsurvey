## 1. Move the export out of views.py

- [x] 1.1 Create `survey/export.py`; move `_answer_cell`, `EXPORT_VALUE_TYPES`,
  `EXPORT_GEOMETRY_TYPES`, `EXPORT_DISPLAY_ONLY_TYPES`, `EXPORT_NO_COLUMN`, `_format_datetime_cell`,
  `_upload_archive_path`, `_sanitize_filename` there; re-export every moved name from `views.py`
- [x] 1.2 Define `ExportBundle` (per geo question: FeatureCollection dict + GEOS geometry per
  feature + section/version metadata; session rows; session metadata rows; object-answer records
  and results GeoJSON per layer; file answers) and `collect(survey, version_surveys,
  excluded_session_ids)` built from the bodies of `_export_survey_data` and `_export_object_answers`
- [x] 1.3 Implement `write_legacy_zip(bundle, zip, prefix)` producing today's entries (GeoJSON per
  question, `objects_*.csv`, results GeoJSON, pandas CSV without BOM, `files/`) with unchanged
  content; `download_data` uses `collect` + `write_legacy_zip` for the default format
- [x] 1.4 Run `CleanExportTest`, `ExportValueCorrectnessTest`, `VersionedDownloadTest`,
  `MultiFileExportTest`, `SharedMapExportTest`, `SurveyExportAuthorizationTest`,
  `DashboardVersionDownloadUITest` — all green before any new format is written

## 2. Scope filters and the URL contract

- [x] 2.1 Extract `completed_session_filter(qs, headers)` in `survey/analytics.py` from
  `PerformanceAnalyticsService._completed_filter_qs`; the service calls it
- [x] 2.2 `download_data`: parse `format` (default `zip`, whitelist, 400 on unknown),
  `completed_only=1` (adds non-completed sessions to `excluded_session_ids` through 2.1),
  `files=1`; emit `data_exported` with the chosen `format` after validation, nothing on 400
- [x] 2.3 Tests (GIVEN/WHEN/THEN): legacy link byte-identical to before; unknown format 400 without
  an event; `completed_only` row count equals the overview's completed count for the same scope;
  `completed_only` + trashed session; viewer-role 404 on `format=xlsx`

## 3. Flat observations table and Excel

- [x] 3.1 `pipenv install openpyxl` from the 3.9 venv; commit `Pipfile` and `Pipfile.lock`
- [x] 3.2 `observations_rows(bundle)`: column order per spec, sub-question columns merged by name
  across questions, `lat`/`lon` from point or centroid, `wkt` for every row, shared-map columns
  only when present
- [x] 3.3 `sessions_rows(bundle)` and `responses_rows(bundle)` (the legacy CSV rows with
  `session_start_utc`), `objects_rows` reusing the object-answer records
- [x] 3.4 `write_xlsx(bundle, path)`: write-only workbook, sheets `observations`, `responses`,
  `sessions`, `objects_<code>`; naive UTC datetimes with `yyyy-mm-dd hh:mm`, numeric cells for
  numbers and lat/lon, bold frozen header, widths from header length clamped 12–40, sheet-name
  sanitiser
- [x] 3.5 Response plumbing: `TemporaryDirectory` + `FileResponse` with cleanup on close;
  `files=1` wraps the single file and `files/` into a ZIP written to disk with chunked upload
  copies; filename `<survey>.xlsx` / `<survey>.zip`
- [x] 3.6 Tests: workbook shape and sheet order; datetime/int/float types survive `openpyxl`
  round trip; two point questions with a shared `Quantity` sub-question give one column and two
  rows with `question` disambiguating; polygon centroid + `POLYGON ((` WKT; blank sub-question
  cell empty; excluded sessions absent; objects sheet present with a `thumbs` vote; xlsx alone is
  a single file with archive paths in photo cells, with `files=1` a ZIP with the xlsx at root;
  temp dir gone after response close

## 4. The export dialog and the naming

- [x] 4.1 `editor/partials/_export_modal.html` (Bootstrap modal): format radios with descriptions
  (Excel, GeoPackage, Shapefile, GeoJSON + CSV archive, KML, CSV; GIS rows behind
  `ogr_available`), version select from `version_choices`, the three switches with hints,
  "Export" primary button; include once on `analytics_dashboard_v2.html`, `analytics_dashboard.html`
  and `editor.html`
- [x] 4.2 `survey/assets/js/export_dialog.js`: read `data-survey-uuid`, `data-version`,
  `data-has-files`, `data-version-choices` from the opener, build the URL, `location.href`,
  remember `localStorage['exportFormat']`; hide the version field for single-version surveys
- [x] 4.3 Replace the Responses "Download" buttons with "Export data" openers (`fa-file-export`,
  tooltip without "CSV + GeoJSON"); `analytics_views` passes `has_files` (any `photo|audio|document`
  question in the family) alongside `version_choices`
- [x] 4.4 `_survey_more_menu.html`: one "Export data" opener carrying the card's uuid, version
  count and choices; remove the per-version and "incl. excluded" link groups; rename the
  `export_survey` group to "Backup (survey file)" with the import hint; `editor.html` provides
  `has_files` per card (one query, like the archived-versions prefetch)
- [x] 4.5 Update `DashboardVersionDownloadUITest` to the dialog markup; add template tests for the
  toolbar button text, the Backup heading, the files switch presence/absence, and the version
  choices rendered in the card opener

## 5. GIS formats through ogr2ogr and CSV

- [x] 5.1 `export.OGR_AVAILABLE = shutil.which('ogr2ogr') is not None`; `download_data` answers 400
  for `gpkg|shp|kml` when False; `analytics_views` and `editor.html` pass `ogr_available` to the
  dialog so the rows are absent
- [x] 5.2 `write_ogr(bundle, driver, out_dir)`: GeoJSON per layer to temp files, deduplicated
  layer names, `subprocess.run(..., check=True, capture_output=True, timeout=120)`; `ExportError`
  with stderr on failure; layer-objects results GeoJSON included as layers
- [x] 5.3 GeoPackage: single `<survey>.gpkg`, `-nln <name>`, `-update -append` after the first
  layer
- [x] 5.4 Shapefile: per-question `.shp/.shx/.dbf/.prj/.cpg` with `-lco ENCODING=UTF-8`, zipped;
  log GDAL's field-name laundering warnings
- [x] 5.5 KML: `LIBKML` single file with `-dsco NAME=<survey>`, one folder per question; fallback to
  `KML` per-question files in a ZIP when the driver is missing (`ogrinfo --formats` check cached)
- [x] 5.6 `write_csv_zip(bundle, path)`: `observations.csv`, `responses.csv`, `sessions.csv`,
  `objects_*.csv`, UTF-8 with BOM, `.` decimal, ISO datetimes; `files=1` appends `files/`
- [x] 5.7 Dialog descriptions: GeoPackage recommended and listed first among GIS formats,
  Shapefile carries the 10-char field-name note and points at GeoPackage
- [x] 5.8 Tests, `skipUnless(OGR_AVAILABLE)`: gpkg layers and feature counts read back with
  `ogrinfo -json`/sqlite equal the legacy GeoJSON; shp ZIP holds exactly five files per question
  and `.prj` names WGS 84; kml parses with two `Folder`s; ogr2ogr failure (patched binary) yields
  500 with stderr in the message and no file; csv BOM present on new CSVs and absent in legacy zip;
  400 for GIS formats when `OGR_AVAILABLE` is patched False

## 6. Close out

- [x] 6.1 i18n: `makemessages -l ru` for every new string, translate, `compilemessages`; verify by
  switching the language cookie, not by reading the `.po`
- [x] 6.2 Full `./run_tests.sh survey` in the worktree; record the delta against the baseline
- [x] 6.3 Manual check (2026-09-29): every format downloaded from the dev server; gpkg and shp read
  back with `ogrinfo` (4 layers, WGS 84, UTF-8 cpg), xlsx with openpyxl, dialog at 390px via
  Playwright; QGIS/Excel GUI opens left to the reviewer
- [x] 6.4 Mark `feature-excel-export.md`, `feature-shapefile-geopackage-export.md`,
  `bug-export-download-confusion.md`, `feature-export-completed-only-filter.md` fixed in
  `openspec/backlog/` with the PR reference
- [x] 6.5 CLAUDE.md: add a "Data export" paragraph naming `survey/export.py`, the collector/writer
  split, the URL contract and the `ogr2ogr` dependency
- [x] 6.6 Draft the Olney reply (flat sheet is live, how to reach it, "session start" caveat) in
  `docs/marketing/user-outreach/olney/correspondence/`; do not send
- [ ] 6.7 Open the PR (`feature/responses-export-formats` → master); after merge
  `/opsx:archive responses-export-formats`
