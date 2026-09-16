# Design: layer-memory-diet

## Context

`survey/layers.py` is the one gate for reference layers (spec reference-overlay-layers,
change overlay-features): `validate_layer_upload` → `objects_from_features` →
`rebuild_layer`. `SurveyMapLayer.geojson` is a derived cache rebuilt from `LayerObject`
rows. The web service runs gunicorn gthread, 2 workers × 4 threads (change
web-concurrency), on Render Standard since #185.

Measured 2026-09-16 (scratchpad probes, kernel VmHWM, synthetic 8.6 MB / 1620-polygon
layer, process starts at 111 MB):

| step | peak | after |
|---|---|---|
| `validate_layer_upload` (decode, `json.loads`, `json.dumps`) | +77 | +27 |
| second `json.loads(geojson_str)` in the view | +55 | +55 |
| `objects_from_features` (1620 GEOS geometries + `bulk_create`) | +43 | +43 |
| `rebuild_layer` (all objects as models, `json.loads` per geometry, `json.dumps`) | +64 | +39 |
| everything freed | | **+107 retained** |
| `_editor_layers` on a fresh process | +55 | +54 retained |
| serve 8.6 MB (`get` + `HttpResponse`) | +16 | +8 once, then 0 |

Worker boot: 0.6 s, 94 MB locally. Celery worker: flat 200–230 MB over four days.

After stage 2 (same probe, same file): `validate_layer_upload` +64 (one parse, no dumps),
`objects_from_features` +36, `rebuild_layer` +26; upload peak +134 MB, retained +71 MB.

After stage 3b, serving the same layer from a fresh process: gzip bytes to a gzip client
2.39 MB on the wire, +6 MB retained once, 0 after; text to a client without gzip 8.74 MB,
+11 MB peak. The ZIP import no longer runs in the web process at all (stage 3a).

## Goals / Non-Goals

Goals: no request parses a multi-megabyte GeoJSON into a Python tree unless it is the
upload itself; the upload holds at most one tree; a worker's high-water mark is
bounded in time; the biggest text the web process touches per layer shrinks ~3.5×.

Non-goals: streaming JSON parsing (ijson) — the 10 MB cap makes one tree acceptable;
changing the layer data model (objects stay the source); S3/CDN delivery of layers.

## Decisions

### D1. Gunicorn `--max-requests 300 --max-requests-jitter 60`, env-tunable
Why: the retained memory is allocator fragmentation, which only a fresh process clears.
At ~2000 requests/day a worker recycles every few hours; boot is under a second; gthread
finishes in-flight requests before exiting and the master starts the replacement first,
so capacity dips by one worker for well under a second. Alternative rejected: `malloc_trim`
hooks or `PYTHONMALLOC=malloc` — fragile, and they do not address pymalloc arenas.

### D2. `property_names` is a stored column, computed in `rebuild_layer`
Why: `_layer_property_names` parsed the whole text to list keys; the keys are already
on `LayerObject.properties`, and `rebuild_layer` already visits every object. Stored as a
sorted list without `RESERVED_PROPS`. Backfilled by the migration from object rows.
`question` layers have no properties → `[]`, as before.

### D3. `layers_for()` defers `geojson`/`geojson_legacy`; readers of the text opt in
Why: thirteen call sites load the text to read a name, a position or a flag. Deferring
in the one resolver fixes them all and makes the next call site safe by default. The
export (`collect_layer_files`) and the gated endpoint call `.defer(None)` / load by pk.
`Model.save()` on a deferred instance saves only loaded fields, so update views keep
working; `rebuild_layer` assigns `geojson` and saves with `update_fields`.
Question → layer FK access (`question.layer`) cannot defer through the descriptor; the
hot paths (respondent section form and POST, Responses aggregates) fetch through a
small `layer_lite(question)` helper or `select_related('layer').defer('layer__geojson', …)`
on the question queryset.

### D4. `validate_layer_upload` returns `(features, property_names)`
Why: the string it built was only ever parsed again. Callers (create view, object-editor
import, ZIP import) use the features directly. The spec sentence "the stored GeoJSON is
the re-serialized parse" stays true: the stored text is `rebuild_layer`'s output.

### D5. `objects_from_features` flushes every 500 rows
Why: the rows list held 1620 GEOS geometries plus model instances until the end;
`bulk_create(batch_size=500)` already writes in batches, so flushing the list at the same
boundary costs nothing and drops the peak by the size of the list. The collision report
and positions are unchanged: `taken` and `start_pos` live outside the list.

### D6. `build_layer_geojson` streams from `values()` rows
Why: the model-instance path (`layer.items` → instances → GEOS → `json.loads` per
geometry → one big tree → `json.dumps`) is the largest single peak. Iterating
`.values('key','title','category','description','link','properties','geometry')` with
`.iterator(chunk_size=500)` and serialising each feature to a string as it arrives keeps
one feature in memory; the collection is `'{"type":"FeatureCollection","features":[' +
','.join(parts) + ']}'`, byte-identical to `json.dumps` of the dict (same key order,
`ensure_ascii=False`, compact separators). Geometry still goes through GEOS
`.geojson`, so coordinates are formatted exactly as today. The same pass collects
`property_names` (D2). `question` layers add `_status` from the row.

### D7. Stage 3a: ZIP import as a Celery job
`SurveyImportJob(user, file, status, warnings, survey, error, created_at, finished_at)`;
the view stores the upload on the private media tier under a random key, enqueues
`run_survey_import(job_id)` and redirects to the dashboard, which renders a job card
(queued / running / done with link / failed with message) and polls it with HTMX while
a job is open. The worker calls the same `import_survey_from_zip` and deletes the file
when done. `CELERY_TASK_ALWAYS_EAGER` in tests keeps the existing import tests
synchronous. Details to be refined when stage 3 starts.

### D8. Stage 3b: gzip-compressed derived GeoJSON
`geojson_gz = BinaryField`; the `geojson` text becomes a property that decompresses on
read and compresses on write so every existing reader and test keeps working; the gated
endpoint serves the bytes with `Content-Encoding: gzip` (browsers and `fetch()` decode
natively; Cloudflare passes origin gzip through). `size_bytes` keeps reporting the
uncompressed size. A migration compresses existing rows and drops the text column.

## Risks / Trade-offs

- D3 turns a silent memory cost into a loud `DeferredAttribute` query when a new reader
  forgets to opt in — acceptable, that is the point; `collect_layer_files` and the endpoint
  are covered by tests.
- D6 must stay byte-identical: a test compares the streamed output with the
  `json.dumps` construction on a fixture layer with covers, categories and a `question`
  layer.
- D8 touches every path that assigns `geojson=` (creates in views, serialization, tests);
  the property keeps them source-compatible, but `.filter(geojson=…)` or
  `.values('geojson')` would break — grep confirms there are none outside tests.

## Migration Plan

Stage 1: migration adds `property_names` (default `[]`) and backfills from objects.
Stage 3: migration adds `geojson_gz`, compresses rows, drops `geojson`; adds the job
model. Each stage is one PR with the previous commit as rollback.
