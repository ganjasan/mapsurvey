# responses-export-formats Specification

## Purpose
The responses export dialog and the formats it produces: the legacy GeoJSON+CSV archive, Excel,
CSV, GeoPackage, Shapefile and KML, the flat observations table (one row per placed feature), the
completed-only and attached-files switches, the URL contract of `download_data`, and the naming
that keeps the data export apart from the survey.json backup. Implementation: `survey/export.py`
(one collector, several writers), `editor/partials/_export_modal.html`, `js/export_dialog.js`.
## Requirements
### Requirement: The export dialog states every choice before the download starts

The Responses page (v2 and legacy dashboards) and the survey card "..." menu SHALL open one export
dialog instead of downloading directly. The dialog SHALL offer: a format (one radio per available
format with a one-line description naming the tool it serves), the version scope as a one-line field
that names what is ticked and opens a panel with a search box, an "All versions" check-box that
ticks or clears them all, and one check-box per version (hidden when the survey has a single
version; "Draft (test)", where offered, is exclusive of the others), and three
switches — "Include excluded responses" (off), "Completed responses only" (off) and "Include
attached files" (off, present only when the survey has file questions). Its primary action SHALL
navigate the browser to a `GET /surveys/<uuid>/download` URL that encodes the choices, so the export
is a copyable link; several ticked versions SHALL travel as one comma-separated `version` value,
every version ticked SHALL send no `version` at all, and with no version ticked the primary action
SHALL be disabled. The last chosen format SHALL be remembered per browser.

#### Scenario: Dialog builds a link, not a request
- **WHEN** a creator picks Excel, "Completed responses only" and version v2 and presses Export
- **THEN** the browser navigates to `/surveys/<uuid>/download?format=xlsx&version=v2&completed_only=1`

#### Scenario: Several versions in one link
- **WHEN** a creator ticks v10 and v11 of an eleven-version survey and picks Excel
- **THEN** the Export link is `/surveys/<uuid>/download?format=xlsx&version=v11,v10`

#### Scenario: All versions is the shortcut
- **WHEN** the creator ticks "All versions", or ticks every version one by one
- **THEN** every version check-box is ticked and the link carries no `version` parameter

#### Scenario: Dozens of versions stay one line
- **WHEN** a survey has 50 versions and the creator types `4` into the panel's search box
- **THEN** the closed field still takes one line, and the panel lists only the versions whose label
  contains `4`

#### Scenario: Nothing ticked
- **WHEN** the creator clears every version check-box
- **THEN** the Export button is disabled until a version is ticked again

#### Scenario: Single-version survey hides the version field
- **WHEN** the survey has no archived versions
- **THEN** the dialog shows no version selector and the URL carries no `version` parameter

#### Scenario: Attached-files switch only when there is something to attach
- **WHEN** the survey has no `photo`, `audio` or `document` question
- **THEN** the "Include attached files" switch is absent from the dialog

#### Scenario: GIS formats absent without ogr2ogr
- **WHEN** the `ogr2ogr` binary is not on the host
- **THEN** GeoPackage, Shapefile and KML are not offered and Excel, CSV and the GeoJSON+CSV archive
  still are

### Requirement: The data export and the survey backup are named apart

Every control that downloads responses SHALL read "Export data". The survey-card menu group that
serves the survey definition file (`export_survey`) SHALL read "Backup (survey file)" and carry a
hint that it is the import format, not the collected data.

#### Scenario: Responses toolbar
- **WHEN** a creator opens the Responses page
- **THEN** the toolbar button reads "Export data" and opens the export dialog

#### Scenario: Card menu separates the two
- **WHEN** a creator opens a survey card's "..." menu
- **THEN** it has an "Export data" entry opening the dialog and a "Backup (survey file)" group with
  "Structure Only", "Data Only" and "Full Backup" pointing at `export_survey`

### Requirement: The download URL accepts a format and keeps the legacy default

`GET /surveys/<slug>/download` SHALL accept `format` with values `zip`, `xlsx`, `csv`, `gpkg`, `shp`,
`kml`. With no `format` or `format=zip` the response SHALL be the legacy GeoJSON+CSV ZIP with
unchanged structure; its per-session CSV SHALL leave out empty sessions like every other format
(see "Empty sessions are never exported"). An unknown value SHALL answer 400. A GIS format on a
host without `ogr2ogr` SHALL answer 400. Authorization, `version` and `include_all` SHALL apply
identically to every format.

#### Scenario: Legacy links unchanged
- **WHEN** a client requests `/surveys/<uuid>/download?version=all` with no `format`
- **THEN** the response is `application/zip` containing one `.geojson` per geo question and the
  per-session CSV with the same columns as before this change, one row per non-empty session

#### Scenario: Unknown format
- **WHEN** a client requests `?format=pdf`
- **THEN** the response is 400 and nothing is exported

#### Scenario: Viewer role required for every format
- **WHEN** a signed-in user with no role on the survey requests `?format=xlsx`
- **THEN** the response is 404, as for the legacy ZIP

### Requirement: The flat observations table has one row per placed feature

The export SHALL produce an observations table with one row per feature of every geo question in
the exported scope, columns in this order: `session_id`, `session_start_utc`, `session_language`,
`validation_status`, `version`, `section`, `question`, `question_code`, `geometry_type`, `lat`,
`lon`, `wkt`, then one column per distinct sub-question NAME across all geo questions (a name shared
by several questions is one column), then `mark_key`, `votes_up`, `votes_down`, `comments` when the
scope contains a shared-map question, then `dot_count`, `area_m2` when the scope contains a `spraycan`
question. A spray cloud is ONE feature: its row has `geometry_type=MultiPoint`, `lat`/`lon` equal
to the cloud's centroid, `wkt` beginning with `MULTIPOINT (`, `dot_count` holding the number of
dots and `area_m2` the area of the cloud's convex hull in square metres; both are empty on rows of
other geometry types. `lat`/`lon` SHALL be the point's
coordinates or the centroid of a line/polygon/cloud; `wkt` SHALL carry the full geometry for every
row. Cells SHALL be formatted by the same rule as the GeoJSON properties (`_answer_cell`), so the
table never disagrees with the GeoJSON.

#### Scenario: Two point questions with a shared sub-question name
- **WHEN** a survey has point questions "White squirrel" and "Fox squirrel", each with a `number`
  sub-question named "Quantity", and one session placed one point on each with quantities 2 and 1
- **THEN** the table has two rows, `question` reads "White squirrel" and "Fox squirrel", one column
  "Quantity" holds 2 and 1, and `lat`/`lon` hold each point's coordinates

#### Scenario: Polygon row carries centroid and WKT
- **WHEN** a respondent draws a polygon
- **THEN** its row has `geometry_type=Polygon`, `lat`/`lon` equal to the polygon centroid and `wkt`
  beginning with `POLYGON ((`

#### Scenario: Spray cloud row carries centroid, WKT and dot count
- **WHEN** a respondent sprays 120 dots on a spraycan question
- **THEN** its row has `geometry_type=MultiPoint`, `lat`/`lon` equal to the cloud centroid, `wkt`
  beginning with `MULTIPOINT (`, `dot_count` 120 and a positive `area_m2`, and those two are the
  last columns

#### Scenario: No spraycan in scope, no dot_count column
- **WHEN** the exported scope has point and polygon questions only
- **THEN** the table has no `dot_count` column, so existing scripts see the same columns as before

#### Scenario: Blank sub-question stays blank
- **WHEN** a feature's sub-question has no answer row
- **THEN** that cell is empty and never holds another question's value

#### Scenario: Excluded sessions are absent
- **WHEN** a session is trashed or `not_approved` and `include_all` is not set
- **THEN** none of its features appear in the table

### Requirement: Excel export is a workbook a clerk can read

`format=xlsx` SHALL return an `.xlsx` workbook with sheets in this order: `observations` (the flat
table), `responses` (one row per session, every non-geo answer, the legacy CSV columns with
`session_start_utc` for the session start), `sessions` (`session_id`, `session_start_utc`,
`session_end_utc`, `language`, `validation_status`, `opened_by_kind`, `version`, `tags`, `notes`),
and one `objects_<code>` sheet per "Objects on the map" question that has sub-questions. Datetime
cells SHALL be Excel datetimes (UTC, column header says so), numeric answers and `lat`/`lon`
numeric cells, everything else text. The header row SHALL be bold and frozen. Sheet names SHALL
satisfy Excel's 31-character and forbidden-character rules.

#### Scenario: Workbook shape
- **WHEN** a creator exports a survey with one point question and one choice question as xlsx
- **THEN** the file opens with `openpyxl`, has sheets `observations`, `responses`, `sessions` in that
  order, and no `objects_*` sheet

#### Scenario: Types survive the round trip
- **WHEN** a session started at 2026-09-22 18:59 UTC placed a point with `Quantity` 3
- **THEN** in `observations` the `session_start_utc` cell is a `datetime`, `Quantity` is the integer
  3 and `lat` is a float

#### Scenario: Objects sheet present when objects were asked about
- **WHEN** the survey has a `layer_objects` question with a `thumbs` sub-question and one answer
- **THEN** the workbook has a sheet `objects_<question code>` with one data row holding the object
  key, title, category and the vote

### Requirement: CSV export is a ZIP of flat tables that Excel reads as UTF-8

`format=csv` SHALL return a ZIP containing `observations.csv`, `responses.csv`, `sessions.csv` and
one `objects_<code>.csv` per qualifying "Objects on the map" question, each UTF-8 with BOM,
comma-separated, `.` decimal, ISO 8601 datetimes. The legacy `zip` format's CSV SHALL keep its
current encoding and layout.

#### Scenario: BOM present on the new CSVs only
- **WHEN** a creator exports as `csv`
- **THEN** every `.csv` in the archive starts with `﻿`, and the CSV inside a `format=zip`
  export of the same survey does not

### Requirement: GeoPackage export holds every layer in one file

`format=gpkg` SHALL return one `.gpkg` with one layer per geo question in scope, named after the
question (sanitised, deduplicated with a numeric suffix), whose features and attributes equal the
GeoJSON the legacy ZIP would contain, plus one layer per "Objects on the map" results GeoJSON. The
conversion SHALL run through the installed `ogr2ogr`; a non-zero exit or a timeout SHALL fail the
request with the tool's stderr in the logged error, never a partial file.

#### Scenario: Two questions, two layers
- **WHEN** a survey with a point question "Sightings" and a polygon question "Zones" is exported as
  gpkg
- **THEN** the file has layers `Sightings` and `Zones` with the same feature counts as the GeoJSON
  files of the legacy ZIP, and `Sightings` features carry the sub-question attributes

#### Scenario: Conversion failure is loud
- **WHEN** `ogr2ogr` exits non-zero
- **THEN** the response is a 500, the error message contains the tool's stderr and no file is
  returned

### Requirement: Shapefile export is a ZIP of per-question shapefiles in UTF-8

`format=shp` SHALL return a ZIP holding, for every geo question in scope, `<name>.shp`, `.shx`,
`.dbf`, `.prj` and `.cpg` with `ENCODING=UTF-8`. Field names longer than 10 characters are
shortened by GDAL; the dialog's Shapefile description SHALL say so and SHALL recommend GeoPackage.

#### Scenario: Complete shapefile set per question
- **WHEN** a survey with one line question is exported as shp
- **THEN** the ZIP contains exactly the five files for that question and the `.prj` describes WGS 84

### Requirement: KML export is one file with a container per question

`format=kml` SHALL return one `.kml` whose root document is named after the survey and holds one
named container (a `Document` with the LIBKML driver, a `Folder` with the KML driver) per geo
question in scope, with sub-question answers as feature data. Invalid geometries (e.g. a
self-intersecting polygon) SHALL be repaired for KML only, so one respondent's shape never fails or
empties the export. Other formats keep geometries as drawn.

#### Scenario: Containers per question
- **WHEN** a survey with two geo questions is exported as kml
- **THEN** the file parses as XML, its root is named after the survey, and it contains two
  `Document` or `Folder` elements named after the questions holding the features

#### Scenario: Self-intersecting polygon
- **WHEN** a polygon question has one self-intersecting answer and one valid answer, and the survey
  is exported as kml
- **THEN** the response is 200, and both placemarks carry geometry
- **AND** the same survey exported as gpkg keeps the self-intersecting polygon unchanged

### Requirement: Completed-only uses the Responses overview's definition

`completed_only=1` SHALL restrict every format to sessions that answered a question of their
version's last section — the same predicate the Responses overview uses for its "completed" count —
through one shared helper, so the exported row count equals the overview's completed count for the
same scope.

#### Scenario: Counts agree
- **WHEN** a survey has 5 clean sessions of which 3 answered the last section
- **THEN** `?format=xlsx&completed_only=1` yields 3 rows in `sessions`, and the Responses overview
  shows 3 completed for the same version scope

#### Scenario: Combined with include_all
- **WHEN** a trashed session answered the last section and the request has `completed_only=1`
  without `include_all`
- **THEN** that session is absent

### Requirement: Attached files ride along only on request

`files=1` SHALL include respondent uploads under `files/<session_id>/` as the legacy ZIP does. For
`xlsx`, `gpkg` and `kml` this SHALL turn the single-file response into a ZIP with the file at its
root next to `files/`; for `csv` and `shp` the files join the existing ZIP. Without `files=1`
these formats SHALL contain the archive path in the file cells and no file content. The legacy
`zip` SHALL keep including files unconditionally.

#### Scenario: Excel alone is a single file
- **WHEN** a survey with a photo question is exported as xlsx without `files`
- **THEN** the response is a single `.xlsx` whose photo cells hold `files/<sid>/<code>__<name>`

#### Scenario: Excel with files is a ZIP
- **WHEN** the same export carries `files=1`
- **THEN** the response is a ZIP containing `<survey>.xlsx` at the root and the photo under `files/`

### Requirement: Memory of an export does not exceed the legacy archive's

`xlsx` SHALL be written in openpyxl write-only mode to a temporary file; `gpkg`, `shp`, `kml` and
every ZIP container other than the legacy one SHALL be assembled on disk and streamed with
`FileResponse`; uploads SHALL be copied into a ZIP in chunks, never read whole into memory. The
temporary directory SHALL be removed when the response closes.

#### Scenario: Temp files cleaned up
- **WHEN** an xlsx export response is fully consumed and closed
- **THEN** the temporary directory it wrote to no longer exists

### Requirement: Empty sessions are never exported

Every format SHALL leave out empty sessions (as defined in `responses-empty-sessions`), whatever
`include_all` and `completed_only` say, through the same shared session gate that applies those
switches. The export dialog SHALL state, under its switches, that sessions without answers are not
exported.

#### Scenario: Empty session absent from every format
- **WHEN** a survey has 3 answered sessions and 2 empty ones and a creator requests
  `?format=xlsx`
- **THEN** the `sessions` sheet has 3 rows

#### Scenario: include_all does not bring them back
- **WHEN** the request has `include_all=1`
- **THEN** the 2 empty sessions are still absent, while trashed and not-approved sessions with
  answers are present

#### Scenario: Dialog says so
- **WHEN** the creator opens the export dialog
- **THEN** it states that sessions without answers are not exported

### Requirement: Spray clouds export as MultiPoint in every format

The GeoJSON of a `spraycan` question (legacy ZIP and `format=zip`) SHALL contain one `MultiPoint`
feature per cloud with the sub-question properties the other geo types carry plus `dot_count` and
`area_m2`.
The GeoPackage, Shapefile and KML writers SHALL emit the question's layer with MultiPoint geometry
through the same `ogr2ogr` call as the other layers; the Shapefile layer type SHALL be
`MULTIPOINT`. The workbook's observations sheet SHALL carry the same row as the CSV table.

#### Scenario: GeoJSON feature per cloud
- **WHEN** two sessions sprayed clouds on the same spraycan question
- **THEN** the question's GeoJSON has two features of type `MultiPoint`, each with `dot_count` and
  `area_m2` properties

#### Scenario: Shapefile layer is MULTIPOINT
- **WHEN** a survey with one spraycan question is exported as shp
- **THEN** the ZIP contains the five files for that question and the `.shp` layer type is
  MULTIPOINT with one record per cloud

