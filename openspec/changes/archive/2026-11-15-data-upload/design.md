## Decisions

**D1 — Workspace layers.** `SurveyMapLayer.survey` becomes nullable; new `organization` FK
(nullable, CASCADE, backfilled from `survey.organization` in the migration). A Data upload creates a
layer with `survey=None, organization=<workspace>`. Every existing reader of survey layers filters by
survey (`layers_for`, `layer_owner`, endpoints), so workspace layers never leak into a survey until
#670 links them.

**D2 — Reading files.** GeoPackage, shapefile (ZIP extracted to a temp dir), KML and GeoJSON are
read with GDAL through `django.contrib.gis.gdal.DataSource`: the first layer, its SRS and fields;
geometries are transformed to EPSG:4326 when the layer has an SRS, and the file is refused when it
has none and its coordinates are outside lon/lat ranges. CSV is read with Python's `csv`
(`utf-8-sig`, sniffed delimiter): coordinate columns by name (`lat/latitude/y`, `lon/lng/longitude/x`,
`easting/x_coord`, `northing/y_coord`); values within lon/lat ranges are WGS 84; values within the
British National Grid envelope (0–700 000 E, 0–1 300 000 N) are EPSG:27700; anything else is refused
with "re-export as WGS 84". Features are yielded as GeoJSON dicts so `objects_from_features` (the
existing, batched importer) creates the objects and `rebuild_layer` derives the GeoJSON.

**D3 — Field dictionary and private columns.** Field types: number when every non-empty value
parses as a number, date when every value is an ISO date, otherwise text; a key candidate is a
field whose values are unique. A column is private when its name matches
email/e-mail/mail/phone/tel/mobile/name of a person (`name` alone is NOT private — it is usually the
object's title) or when more than half of its values look like emails or phone numbers.
`Dataset.fields = [{'name', 'label', 'type', 'private'}]`.

**D4 — The job.** `DataImportJob(organization, user, file on the private tier under
data_imports/<uuid>, original_name, status queued|running|done|failed, dataset, report JSON, error,
timestamps)`; `data.tasks.run_data_import` runs once per job (a redelivered message finds the row
past `queued`), deletes the file at the end, records the report. Limits are checked from the
workspace entitlement before enqueuing (size) and in the worker (features).

**D5 — Catalogue.** Workspace datasets (no survey) are visible to every member. The upload control is
a `<label>` around a hidden file input that submits on change (one click, no extra step); job cards
reuse the dashboard import-card behaviour (poll every 3 s while open, dismiss when finished).

## Risks / Trade-offs

- [Big datasets and memory] → import only in the worker, batched object creation, gzip storage; a
  dataset larger than the survey layer caps cannot reach a respondent map (#670 enforces).
- [CRS guessing for CSV] → only lon/lat and BNG are guessed; everything else is refused with a fix.
