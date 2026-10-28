## Context

Geo answers today are single-part geometries in three typed columns on `Answer` (`point`, `line`,
`polygon`, `survey/models.py:1140-1142`); each placed feature is its own top-level `Answer` row
and sub-answers hang off it by `parent_answer_id`. Almost every consumer leans on the convention
"column name == `input_type`": `getattr(answer, question.input_type)` (`views.py:891`),
`f'{input_type}__isnull'` (`analytics.py:682`, `public_results.py:294`), and the expression
`a.point or a.line or a.polygon` (`analytics.py:564,999,1017`, `public_results.py:305`,
`layers.py:643`). The type sets live in `survey/question_types.py` (`GEO_TYPES`, `PARENT_TYPES`,
`MAP_ONLY_TYPES`, `PICKER_TYPES`), but a dozen places still carry a literal
`('point','line','polygon')` (inventory in tasks.md §1). The respondent map JS is all inline in
`base_survey_template.html` (Leaflet 1.4.0 + Leaflet.draw 1.0.4 from CDN); polygon/line drawing
uses `L.Draw.*`, points use the crosshair overlay, both finish into the shared `draw:created`
handler, `editableLayers` FeatureGroup and the `|`-joined `Feature` chunks the section POST
splits (`views.py:1128`). `restoreGeoAnswers` and every Responses/public map branch on
`geometry.type === 'Point'` and otherwise fall to `L.geoJSON`. `leaflet.heat` is loaded from CDN on
the two analytics dashboards and the public page, not on the respondent page; its heat is
Point-only (`analytics_geo_map.html:402`).

A spray cloud breaks two assumptions at once: it is a multi-part geometry, and it is dense
(hundreds to thousands of vertices per answer) — one Leaflet marker per dot or one `Answer` row
per dot is not an option.

## Goals / Non-Goals

**Goals**
- `spraycan` as a first-class geo type: one `Answer` row per respondent holding a `MultiPoint`.
- Replace the "column == input_type" convention with ONE mapping so the fourth type cannot be
  missed by the next reader.
- Paint mode that works with a finger: explicit tool switch, no accidental panning, no page
  scroll.
- Density, not shapes, on every read surface; respondents weighted equally; public page never
  ships raw dots.
- Every parity test (`QuestionTypePickerMetadataTest`, `QuestionSubtextRenderingTest`,
  `AIGeneratorKnowsEveryTypeTest`, picker-group tests) green.

**Non-Goals**
- Map-Me stroke metadata (order/timing/brush per stroke); several clouds per respondent;
  `min_features`/`max_features` for spraycan.
- Spraycan as a shared-map source question; spraycan in the layer object editor.
- Keyboard-only painting (a11y) — recorded as a follow-up.
- Vendoring `leaflet.heat` (stays on CDN as today).

## Decisions

### 1. Storage: `Answer.multipoint` + a geometry-column map, not a generic geometry column

`Answer.multipoint = MultiPointField(null=True, blank=True)` (srid 4326 like its siblings), one
migration (`0092`). A generic `GeometryField` would force a data migration of every existing
answer and break the typed-column reads on which export, analytics and public results rely.

Add to `survey/question_types.py`:

```python
GEO_TYPES = ("point", "line", "polygon", "spraycan")
GEO_COLUMNS = {"point": "point", "line": "line", "polygon": "polygon", "spraycan": "multipoint"}
def geo_column(input_type): ...
```

and `Answer.geometry` property (`getattr(self, GEO_COLUMNS[self.question.input_type])`
falling back to the first non-null geo column). Every `getattr(answer, input_type)`,
`{input_type}__isnull` and `point or line or polygon` site switches to `geo_column()` /
`answer.geometry`. `SurveyHeader.geo_questions()`, `layers.GEO_INPUT_TYPES`,
`public_results.GEO_INPUT_TYPES`, `export.EXPORT_GEOMETRY_TYPES`, `ai/validator.GEO_INPUT_TYPES`
all become imports of `question_types.GEO_TYPES` — except `layers.py`'s source-question set,
which deliberately stays `("point","line","polygon")` as `SHARED_MAP_SOURCE_TYPES` (Non-goal).

### 2. Brush size is a `Question` field with one px map

`Question.spray_brush = CharField(choices=small|medium|large, default="medium")` is the DEFAULT —
the paint toolbar carries an S/M/L switch for the respondent (owner decision 2026-10-04), fed by
`data-brush-sizes` on the button so the px map has one source.

`SPRAY_BRUSH_PX = {"small": 20, "medium": 40, "large": 70}` in `question_types.py`, rendered
as `data-brush-px` on the draw button. A model field (not `validation_settings`) because
`validation_settings` is not serialized in the survey ZIP today (`serialization.py:194-226`),
and the brush must round-trip. No dot cap by default (owner decision 2026-10-04): an optional
`validation_settings['max_dots']` per question reaches the page as `data-max-dots`;
`SPRAY_HARD_CEILING` (100 000) bounds scripted POSTs only.

### 3. Paint mode is a new mode in the existing state machine, with its own canvas layer

New static file `survey/assets/js/spray_layer.js` defining `L.SprayLayer` (a `L.Layer` owning
one `<canvas>` in `overlayPane`; `dots: L.LatLng[]`; `redraw()` on `moveend`/`zoom`/`resize`
draws each dot as a 4 px disc at alpha 0.35 in the question colour; `toGeoJSON()` returns a
`Feature<MultiPoint>` with `properties.question_id`; `getBounds()`, `getCenter()` (mean of
dots) and `hitTest(latlng, px)` for popups and selection). Reused verbatim by the respondent
page, the Responses drawer/modal and the question preview frame.

In `base_survey_template.html` a `.drawspray` click handler enters paint mode:
`map.dragging.disable()`, `touchZoom`/`boxZoom`/`doubleClickZoom` off, container gets
`touch-action: none` and a `spray-mode` class (cursor hidden, a brush ring follows the pointer),
pointer events (`pointerdown/move/up/cancel` with `setPointerCapture`) on the container drive
the active tool. Spray: on each `pointermove` and on a 60 ms interval while down, emit 6 dots
uniformly on the disc (`r = R·√u`, `θ = 2πv`) around the pointer, converted with
`map.containerPointToLatLng`; stop at the creator's `max_dots` (if any) and show the hint. Erase: drop dots within
`R` px of the pointer. Move map: re-enable dragging/zoom and ignore pointer events. `#drawbar`
gains a tool segment and Clear; Finish calls `endPaintMode(true)` which fires the same
`draw:created` with `layerType: 'spray'` and the `L.SprayLayer` as `layer`, so popups, counters,
`editableLayers` and HTMX serialization are untouched. Cancel restores the previous layer.
Edit from the popup re-enters paint mode seeded with the layer's dots; Delete goes through the
existing delete path. `startEditMode()` skips layers without `.editing`.

Why pointer events and not Leaflet's own handlers: Leaflet 1.4 synthesises `click` from touch
with delays and swallows `touchmove` for dragging; `pointer*` + `setPointerCapture` is the only
way to get a continuous stroke on iOS Safari and Android Chrome without fighting it.

### 3a. Rendering is sprite stamping; storage is normalised dots (owner direction 2026-10-04)

Three requirements pull apart — look like a graphics editor, stay light on weak devices, stay
analysable in GIS — and the split is: **render like an editor, store like a GIS**.

- *Look*: GIMP's and Krita's airbrush stamp a soft brush sprite with low alpha; density is
  accumulation. `L.SprayLayer` pre-renders ONE sprite per colour (radial halo fading to
  transparent + a near-opaque grain) and `drawImage`s it per dot; scatter is a 2-D Gaussian
  (σ = r/2.2) clipped to the ring. The result reads as airbrush: solid where dwelt, soft at the
  edge, grainy throughout.
- *Weight*: a sprite blit is compositor work — 30 000 dots redraw in ~90 ms even in a
  software-rendered headless browser, far less on a phone GPU — and redraws happen only on
  `moveend`/`zoomend` (the canvas rides the overlay pane during a drag); a stroke paints only
  its new dots. No WebGL, no workers; they would not pay for themselves at this size.
- *Analysis*: the stored thing stays a `MultiPoint` (every GIS reads it; heat, grid,
  k-anonymity all work on points) but is NORMALISED on save (`survey/spray.py`): snapped to a
  1 m grid, duplicates dropped, order kept. A dot is otherwise an artefact of the pointer's
  event rate; after normalisation the count is a function of painted area and dwell — paint
  saturates at one dot per square metre, exactly like an editor's canvas. Two derived numbers
  travel with every cloud (`dot_count`, `area_m2` = convex-hull area) in the table, the drawer
  and the export, so clouds can be filtered and compared without a GIS.
- *Rejected for now*: storing strokes (Map-Me's model) as the source and deriving dots. It is
  the richer record (time over place), but every GIS consumer would still need derived points
  produced deterministically on the server; keep it as an additive JSON log if "time over
  place" analysis is ever asked for. Also rejected: a raster/grid as the source — the brush is
  a screen size, so the resolution a respondent paints at is not known up front.
- *Next for analysis* (separate change, all derivable from the stored points): consensus
  contours ("cells painted by ≥ X % of respondents" as polygons via GDAL contour), a GeoTIFF
  density raster for QGIS users, and group comparisons on the same grid.

### 4. POST and restore: same chunk format, new branch

The HTMX serializer already posts `JSON.stringify(layer.toGeoJSON()) + "|"`, so a cloud arrives
as one `Feature<MultiPoint>` chunk. `views.py` branch (`:1127-1159`): `if input_type in
GEO_TYPES`; for `spraycan` clamp to ONE chunk, build `MultiPoint`, truncate to
the creator's `max_dots` or `SPRAY_HARD_CEILING`, assign via `setattr(answer, geo_column(...), geom)`. Invalid coordinates raise
through `GEOSGeometry` like today's malformed chunks — but NOT skipped silently: a MultiPoint with
out-of-range coordinates is rejected with the geo validation error (the spec requires it; today
only unparsable chunks are skipped). `_build_section_context` (`:877-920`) uses `answer.geometry`,
so `existing_geo_answers` carries the MultiPoint; `restoreGeoAnswers` gains a `MultiPoint` branch
that builds an `L.SprayLayer`. `sync_question_layers_for_session` ignores spraycan (Decision 1).

### 5. Responses map: the cloud is one vote per cell, the session is the unit

`analytics.get_geo_feature_collection` emits `MultiPoint` features with
`properties.dots = n`. In `LayerManager.init`, a slot whose first feature is `MultiPoint` becomes
kind `spray`: no vector layer; an `L.SprayAgreementLayer` over all clouds — per screen cell the
share of respondents whose cloud touches it, drawn as crisp geographic cells in the layer's
colour with opacity by share — the public page's grid, which the owner picked over both the
heat ramp and a single-hue smooth surface on 2026-10-04; the creator and the public now read the
same picture. Cells are sized by the clouds' extent like `public_results_grid` and indexed in
projected world pixels, so they stay put across pans and zooms; edges snap to whole pixels so
translucent neighbours neither overlap nor gap. A `heat` style (box-blurred share through the
classic ramp, drawn as one cell-sized offscreen image scaled up with bilinear smoothing) stays in
the layer as an option — plus an invisible proxy marker per
session (cloud centre, with `getBounds` = cloud bounds) for selection, filtering and fit-to-data.
`leaflet.heat` was tried first and rejected for this: it scales intensity by
`2^(maxZoom − zoom)`, so with `maxZoom` 23 every cell sat on the opacity floor and the surface
was a flat blob, and its weights cannot express "count each respondent once per cell". The
agreement statistic is also exactly what the public page publishes as a grid, so the creator and
the public read the same picture. `createHeat` is a no-op for `spray` slots; legend icon
`fa-spray-can`; the Overview thumbnail builds the same layer from the MultiPoint features. Drawer (`analytics_dashboard_v2.html:1196`), session modal
(`analytics_session_detail.html:138`) and Overview thumbnail (`analytics_overview_pane.html`)
get a `MultiPoint` branch → `L.SprayLayer` (dots, not heat — one session is a picture, not a
density). `_format_cell` prints "N dots". `_stats_geo` dispatch adds `spraycan`.

### 6. Public results: server-side grid, k-anonymity by omission

`_map_payload` branches on `spraycan`: load clouds of clean sessions, transform to EPSG 3857,
cell size `max(20 m, longer_side / 40)` of the union bbox, bin every dot, count DISTINCT sessions
per cell, drop cells `< k`, emit `data_type: 'grid'`, `cells: FeatureCollection<Polygon>` with
`respondents`, `max`, `respondents_total`, `cell_m`. Omission rather than "<K": a "<3" cell says
exactly where one person sprayed. `PUBLIC_RESULTS_SNAPSHOT_VERSION = 2`. `public_results.html`
`renderMap` draws `grid` as `L.geoJSON` with fill opacity `0.15 + 0.6·respondents/max`;
`public_results_editor.py` hides `map_viz_options` and label-field checkboxes for spraycan
blocks. Binning uses GEOS in Python (clouds are ≤ 3000 dots × sessions; fine for the 60 s live
cache), no PostGIS SQL.

### 7. Export: fourth geometry type, one extra trailing column

`EXPORT_GEOMETRY_TYPES` from `GEO_TYPES`; `GEOMETRY_TYPE_NAMES['spraycan']='MultiPoint'`,
`OGR_GEOMETRY_TYPES['spraycan']='wkbMultiPoint'`; `_collect_part` reads `answer.geometry` and
adds `dot_count` to properties; `observation_rows` centroid works for MultiPoint via
`geom.centroid`; `dot_count` column appended after the shared-map columns only when a spraycan
question is in scope (keeps every existing column index). Shapefile `MULTIPOINT` is supported by
the ESRI driver; verify in `ExportOgrFormatsTest`.

### 8. Editor, serialization, AI

Picker: `PICKER_TYPES['spraycan']` group `geo`, icon `fas fa-spray-can`, label "Spray area".
Modal: `fg-spray_brush` shown for `spraycan`; `fg-icon_class` and `#vs-geo-fields` hidden for
it (`toggleTypeScopedFields` / `toggleValidationFields` read the JS mirrors of `GEO_TYPES`, so
add a `SPRAY_TYPES` mirror rather than a literal). `SUBQUESTION_DISALLOWED_INPUT_TYPES`
(`editor_forms.py:12`, `editor_clipboard.js:25`) gain `spraycan`. `_serialize_question` /
`_create_question` carry `spray_brush` with default + report line; `_serialize_answer` /
`create_answer` carry `multipoint` as WKT. `cloning.py` copies the field generically (verify).
AI: `prompts.py` gains the type description and the "fuzzy vs bounded" guidance;
`validator.py` requires colour, no icon; `materialize.py` passes the default brush; one example
chip in the brief panel.

### 9. Preview and widget

`SprayDrawButtonWidget(draw_type='drawspray', template 'spray_draw_button.html')` with
`brush_px`; `_get_form_from_input_type` branch; the question preview frame includes
`spray_layer.js` and renders a canned 150-dot cloud.

## Risks / Trade-offs

- **[Risk] Leaflet.draw's edit/delete toolbar and `startEditMode` iterate `editableLayers` and
  expect `.editing`** → `L.SprayLayer` exposes a no-op `editing` object; edit for sprays goes
  through paint mode only. Covered by a browser check, not a unit test.
- **[Risk] Pointer capture on iOS < 13 is absent** → fallback to `touch*` listeners with
  `preventDefault`; the page already requires modern browsers for Leaflet 1.4.
- **[Risk] 3000 dots × thousands of sessions on the Responses map** → heat is built from
  flattened coordinates once per slot (~3 MB JSON per 1000 sessions at the cap); acceptable for
  the creator surface, and the per-question `max_dots` is the knob when a survey needs one. The public page never pays it (grid).
- **[Trade-off] Dot-count cap truncates silently on the server** → the client stops at the same
  cap and says so; the server rule is a backstop for scripted posts.
- **[Trade-off] Grid cell size derived from data extent** → a survey over a whole region gets
  coarse cells. Deterministic and explainable; a per-block override is a follow-up if asked.
- **[Risk] Snapshot version bump invalidates every frozen page's blocks** → the notice is the
  designed behaviour (`PUBLIC_RESULTS_SNAPSHOT_VERSION` exists for exactly this); the changelog
  entry says "re-freeze".
- **[Trade-off] Respondent page gains one more inline mode in a 1100-line template** → the
  canvas layer is a separate static file; the mode wiring stays inline next to its siblings
  rather than starting a half-extraction.

## Migration Plan

1. Migration `0092`: `Answer.multipoint`, `Question.spray_brush` — additive, no data step, safe
   in pre-deploy (no `RemoveField`, see the pre-deploy lesson).
2. Deploy; old answers untouched; frozen public pages with map blocks show the re-freeze notice
   once (version bump) — creators click re-freeze.
3. Rollback: revert the deploy; the two new columns stay unused and harmless.

## Open Questions

- Brush ring colour on dark basemaps — use the question colour with a white halo (as the
  crosshair pin does)? Decide in the browser.
- Should the Responses heat radius for spray slots default larger than for point slots? Try
  `HEAT_DEFAULTS` first, tune on a real survey.
