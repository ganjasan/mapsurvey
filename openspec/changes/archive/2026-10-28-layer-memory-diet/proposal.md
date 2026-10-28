# Proposal: layer-memory-diet

## Why

On 2026-09-15 the web service ran out of memory (see change `web-plan-standard`). The
plan bump bought headroom; this change removes the cause. Measured on a synthetic layer
the size of the one that tipped production (8.6 MB, 1620 polygons), one process:

| path | peak | left behind |
|---|---|---|
| layer upload (validate loads+dumps, second `json.loads`, GEOS rows, `rebuild_layer`) | +198 MB | +107 MB |
| editor page render (`_editor_layers` parses every layer for property names) | +55 MB | +54 MB |
| serving the 8.6 MB text to a respondent | +16 MB | +8 MB once |

The "left behind" column is the memory story: a 55 MB tree of dicts, lists and floats
fragments the allocator arenas, and a gunicorn worker that is never recycled keeps them
for its whole life. Two uploads on two workers were the 512 MB limit. Nothing leaks in
the strict sense (the Celery worker is flat, repeated serves add nothing); the process
ratchets up to its largest request and stays there.

## What changes

Three stages, each shippable on its own.

**Stage 1 — stop the ratchet.** Gunicorn recycles workers (`--max-requests` with jitter,
env-tunable like the other gunicorn knobs). `SurveyMapLayer.property_names` is stored at
`rebuild_layer` time so the editor never parses a layer to list its properties.
`layers_for()` defers the geometry columns by default; the two export sites that need
the text ask for it explicitly, and the gated endpoint keeps loading it. Question → layer
accesses on respondent and Responses paths go through a deferred fetch.

**Stage 2 — upload diet.** `validate_layer_upload` returns the parsed features (no
`json.dumps` of a string that only gets parsed again), `objects_from_features` writes in
batches of 500 instead of holding every row, and `build_layer_geojson` streams the
FeatureCollection from `values()` rows one feature at a time — byte-identical output,
no model instances, no whole-collection tree.

**Stage 3 — structure.** ZIP import runs on the Celery worker as a tracked job with a
dashboard status card (it already takes 17 s and hits client timeouts). The derived
GeoJSON is stored gzip-compressed and served with `Content-Encoding: gzip` (8.6 → 2.4 MB
per row, per request and per response).

## Out of scope

The `purge_survey` `ProtectedError` on layer-bound questions (separate bug). Moving the
single-layer upload from the settings card to a job: after stage 2 its peak fits the
2 GB instance many times over and the synchronous card UX stays.

## Impact

- Specs: `render-deployment` (ADDED worker recycling), `reference-overlay-layers`
  (MODIFIED upload; MODIFIED gated endpoint for stage 3), `survey-serialization`
  (MODIFIED import via Web UI for stage 3).
- Migrations: `property_names` (stage 1), `geojson_gz` + import job model (stage 3).
- No kill switch (owner rule): each stage is a plain code change with the previous
  commit as the rollback.
