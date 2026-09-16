# Tasks: layer-memory-diet

## 1. Stage 1 — stop the ratchet

- [x] 1.1 Gunicorn `--max-requests ${GUNICORN_MAX_REQUESTS:-300} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-60}` in `Dockerfile` CMD and `docker-compose.yml`; declare both in `render.yaml`
- [x] 1.2 `SurveyMapLayer.property_names` JSONField + migration with backfill from `LayerObject.properties`
- [x] 1.3 `rebuild_layer` computes `property_names`; `_layer_property_names` and the create response read the column
- [x] 1.4 `layers_for()` defers `geojson`/`geojson_legacy`; `collect_layer_files` and the gated endpoint opt in; layer `get_object_or_404` sites in editor/object views defer
- [x] 1.5 Question → layer accesses on respondent form/POST and Responses paths go through a deferred fetch
- [x] 1.6 Tests: property names stored and backfilled; editor page and settings card render without selecting the geometry column; export still carries the text; Dockerfile/compose carry the recycling flags
- [x] 1.7 Follow-up (found on production 2026-09-16): stock gthread 502s one request per recycle and per deploy switch; `mapsurvey.gunicorn_workers.DrainingThreadWorker` stops accepting before it exits and drains what it accepted; `scripts/gunicorn_recycle_check.py` reproduces (stock: 11/12/88/1 failures over keep-alive, fresh-connection, four-parallel-client and SIGTERM runs; draining: 0/0/0/0); guard test names the class

## 2. Stage 2 — upload diet

- [x] 2.1 `validate_layer_upload` returns `(features, property_names)`; create view, object-editor import and ZIP import use the features
- [x] 2.2 `objects_from_features` flushes rows every 500
- [x] 2.3 `build_layer_geojson` streams from `values()` rows and collects property names in the same pass
- [x] 2.4 Tests: validation contract; streamed output byte-identical to the dict construction (upload layer with covers and categories, `question` layer with `_status`); collision report unchanged across batch boundaries
- [x] 2.5 Re-run the memory probe: upload peak +198 → +134 MB (kernel HWM), retained after the upload +107 → +71 MB; the single remaining large item is the one parse tree (+64 MB), which the 10 MB cap bounds

## 3. Stage 3 — structure

- [x] 3.1 `SurveyImportJob` model + migration; `import_survey` view stores the file and enqueues `run_survey_import`; dashboard job card with HTMX polling
- [x] 3.2 `geojson_gz` BinaryField, `geojson` property, migration compressing existing rows; gated endpoint serves `Content-Encoding: gzip` to clients that accept it, text to the rest
- [x] 3.3 Tests: job lifecycle (queued → done / failed, warnings shown, file removed); gzip round-trip, endpoint headers and content negotiation, ETag/304 unchanged; the tallies path reads through the property
- [ ] 3.4 Full suite green; CLAUDE.md notes for `layers_for` deferral, `property_names`, gzip storage and the import job
