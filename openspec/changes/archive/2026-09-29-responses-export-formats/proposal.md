## Why

The responses download is shaped for a GIS desk and nobody else: one `.geojson` per geo question
plus a CSV of the NON-geo answers, one row per session. For a survey whose whole payload is pins
the openable file is the empty one and the informative ones have no handler on a Windows machine
without a GIS. City of Olney (paying, $490/yr) reported exactly that on 2026-09-19 ("the Excel
sheet was not as informative, and the other files are at type my computer cannot open") and needs a
flat sheet of observations before the count goes year-round on 2026-10-03. GIS users pull the other
way: lead-119 (Berlin Senate) asked for Shapefile/GeoPackage as "very important", and he also
mistook the survey backup ("Export") for the data download and reported GeoJSON as broken.

Four backlog cards describe one surface — what the export dialog offers and what it produces:
`feature-excel-export`, `feature-shapefile-geopackage-export`, `bug-export-download-confusion`,
`feature-export-completed-only-filter`. This change closes all four.

## What Changes

- **Export dialog** replaces the bare "Download" link on the Responses page (both the v2 and the
  legacy dashboard) and the download entries of the survey card "..." menu. Fields: format, version
  scope, "include excluded responses", "completed responses only", "include attached files". It
  builds a GET URL to the existing `download_data` view, so every export stays a copyable link.
- **Excel (`.xlsx`)** format: sheets `observations` (one row per placed feature: session, question,
  sub-question answers, lat/lon, WKT), `responses` (one row per session, the current CSV),
  `sessions`, and `objects` when the survey asks about layer objects. Real dates and numbers, frozen
  bold header, sensible column widths.
- **Flat observations table** as a first-class output, also as `observations.csv` inside the CSV
  format. This is the shape Olney asked for and the one every non-GIS municipal customer needs.
- **GeoPackage, Shapefile, KML** formats produced by `ogr2ogr` (GDAL is already in the image for
  GeoDjango) from the GeoJSON the export already builds. GeoPackage is the recommended GIS format
  (one file, one layer per question); Shapefile ships as a ZIP with UTF-8 encoding and the 10-char
  field-name truncation stated in the dialog.
- **"Completed responses only"** filter (`completed_only=1`), using the same completion definition as
  the Responses overview (answered the version's last section), so the two never disagree.
- **Naming**: the data download is "Export data" everywhere; the survey.json backup group in the
  "..." menu becomes "Backup (survey file)" with a one-line hint that it is the import format, not
  the data. Existing URLs keep working: `download` with no `format` returns today's ZIP unchanged.
- `data_exported` carries the chosen `format` instead of the constant `'zip'`.
- Export code moves out of `survey/views.py` into `survey/export.py`: one collector that builds an
  intermediate bundle from the database, several writers that serialise it. Behaviour of the legacy
  ZIP is preserved byte-for-byte in content (tests already pin it).

## Capabilities

### New Capabilities
- `responses-export-formats`: the export dialog, the format catalogue (legacy GeoJSON+CSV ZIP,
  Excel, CSV, GeoPackage, Shapefile, KML), the flat observations table, the completed-only and
  attached-files options, the naming of data export vs survey backup, and the URL contract of
  `download_data`.

### Modified Capabilities
- `version-export-ui`: the version-aware download entries in the survey card menu open the export
  dialog with the version preselected instead of downloading directly; the "Export" group is
  renamed to distinguish the survey backup from the data export.
- `creator-distribution-events`: `data_exported.format` is the format the creator chose
  (`zip | xlsx | csv | gpkg | shp | kml`), not always `'zip'`.

## Impact

- `survey/views.py` (`download_data`, `_export_survey_data`, `_export_object_answers`,
  `_answer_cell` and the classification sets) → `survey/export.py`; views keep thin re-exports for
  the tests that import them.
- New dependency `openpyxl` (pure Python) in `Pipfile`. `gdal-bin` (`ogr2ogr`) is already installed
  by the `Dockerfile`; GIS formats are offered only when the binary is present on the host.
- Templates: `editor/analytics_dashboard_v2.html`, `editor/analytics_dashboard.html`,
  `editor/_survey_more_menu.html`, `editor.html` (dashboard modal host), new
  `editor/partials/_export_modal.html`; JS `survey/assets/js/export_dialog.js`.
- `survey/analytics.py`: the completed-session filter becomes a module-level helper shared with the
  export.
- i18n: new creator-facing strings in the EN/RU catalogs.
- Tests: existing `CleanExportTest`, `ExportValueCorrectnessTest`, `VersionedDownloadTest`,
  `MultiFileExportTest`, `SharedMapExportTest`, `DashboardVersionDownloadUITest` must keep passing
  against the moved code; new tests for each format, the observations table, the completed filter
  and the dialog markup.
- Memory: the XLSX is written in openpyxl write-only mode to a temp file and streamed with
  `FileResponse`; `ogr2ogr` runs on temp files. Nothing new is held in the worker beyond what the
  legacy ZIP already holds.
- Backlog: `feature-excel-export`, `feature-shapefile-geopackage-export`,
  `bug-export-download-confusion`, `feature-export-completed-only-filter` are closed by this change.
