## Why

Councils keep their registers as GeoPackages, zipped shapefiles, KML and spreadsheets with
eastings and northings in a national grid; today Mapsurvey takes only a GeoJSON under 10 MB
uploaded into one survey. Data Vision FE-3 (#668, epic #676): a file becomes a workspace dataset in
one step, without converting it in QGIS first.

## What Changes

- **"+ New dataset"** on the Data catalogue: one click opens the file picker; the upload becomes a
  background import job (never parsed in a web request) with a card on the catalogue that refreshes
  until it is done.
- Formats: GeoPackage, zipped shapefile, KML, GeoJSON, and CSV with latitude/longitude or
  eastings/northings columns. Files with a coordinate system are reprojected to WGS 84; a CSV in
  British National Grid is recognised by its value ranges; any other projected CSV is refused with
  a message saying how to export it.
- Field types are guessed; columns holding emails, phone numbers or personal names are marked
  **private** (owner default); rows without a location and duplicate keys are listed in the result,
  never fatal. The result card names the counts, the coordinate system and the private columns.
- Limits (owner defaults): Free 10 MB and 5,000 features; Pro 50 MB and 100,000 features.
- A workspace dataset needs no survey: `SurveyMapLayer.survey` becomes optional and the layer
  gains its workspace (`organization`, backfilled). An uploaded dataset is `private` until its
  owner releases it; it can be put on a survey's map only within the survey layer limits
  (#670).
- `Dataset.fields` holds the field dictionary (name, label, type, private) that #669 makes
  editable.

## Capabilities

### New Capabilities
- `data-upload`: turning a file into a workspace dataset — formats, reprojection, limits, the job,
  the report, private columns.

### Modified Capabilities
- `data-catalogue`: workspace datasets without a survey appear to every member.

## Impact

- Migrations: `survey` (layer `survey` nullable, `organization` FK + backfill), `data` (`fields`,
  `DataImportJob`). Code: `data/imports.py`, `data/tasks.py`, `data/views.py` (upload, job card,
  dismiss), catalogue template, `data/datasets.py` (workspace layers). No change for existing survey
  layers: every query that lists a survey's layers already filters by survey.
- Tests: `survey/tests/test_data_upload.py`.
