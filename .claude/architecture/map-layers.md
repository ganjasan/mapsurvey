# Reference layers, layer objects, shared maps, coverage, layer style

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Placements, layers in Data, the study area (change `map-layers-study-area`, #779, #303)** — read this
first; it overrides the older notes below where they disagree.
- **A layer is on a section's map only through a `LayerPlacement`** (canonical survey, layer, scope `all`
  | `sections`, section refs, position). `layers.section_layer_ids(section)` reads placements only;
  `placements_for(survey)` gives them in stacking order. Scope `all` covers every map section incl.
  ones added later; `sections` names refs `<code>`/`<code>#<n>` from `survey.section_refs` (the
  translation table's numbering; `<code>` ≡ `<code>#0`). The ONE writer is
  `survey/services/placements.py` (editor Map card, Survey settings, Objects question save, REST
  `api/v1/map.py`, MCP `mcp/tools/map.py`). Placement is a SAFE edit: in place on a live survey, no
  draft, never copied by draft/publish/restore; `clone_survey` copies the rows.
- **Questions never show a layer.** An Objects question or a budget only asks; its save calls
  `placements.ensure_on_section`. Legacy legend-only questions (`panel_mode='legend'`, no
  sub-question; `models.legend_only_q()`) are hidden everywhere (`SurveySection.questions()`, the
  editor lists) until release PR 2 deletes them and drops `panel_mode` / `hidden_layers` /
  `show_tallies` / `show_comments`.
- **Uploaded and drawn layers live in Data**: `services.layers.new_layer` creates a workspace layer
  (`survey=NULL`), its `public` Dataset row and a `DatasetLink` to the canonical survey, then
  `place(scope='all')`. A survey OWNS only its shared-map (`question`) layers (and, without a
  workspace, its uploads). So `layers_for(survey)` (links + own) is also what the survey's own write
  paths address (`services.layers.layers_qs`, the layer card, object editor, REST, MCP) — the old
  "write paths keep owner.map_layers" rule is gone. `services.layers.delete(actor, layer, survey)`
  deletes an owned layer but only unlinks + unplaces a dataset (it stays in Data); deleting a survey
  keeps its datasets. Migration 0136 moved every existing upload layer this way.
- **Uploads**: a WGS 84 GeoJSON keeps the direct parser (properties as JSON values); a projected
  GeoJSON and GPKG/zipped SHP/KML/CSV go through the Data reader (`data.imports.open_source`,
  reprojected); the response names `converted_from` and `looks_like_boundary` (1–3 polygons).
- **Study area** = `StudyArea` (one per canonical survey, MultiPolygon ≤2,000 vertices, fog,
  refuse_outside, message per language, refused_marks). ONE writer `survey/services/study_area.py`.
  Place lookup `survey/study_area_lookup.py` (Nominatim `polygon_geojson`, 30-day cache, 1 req/s,
  editor only): polygon as is, line → `ST_Buffer` geography corridor 50/100/200 m, point → rectangle.
  Editor page `study_area_views.editor_study_area` + `js/study_area_editor.js`. Respondent outline
  from the gated `survey_study_area_geojson` (a FeatureCollection, never inlined); `js/study_area.js`
  draws fog/outline, opens the map on the area, and refuses outside marks in `draw:created`
  (`StudyArea.admit`, after `BudgetQuestion.admit`). The section POST re-checks through
  `survey/study_area_guard.py` (PostGIS 5 m buffer once per POST, prepared GEOS per mark; spray
  clipped; refusals skipped + counted, never an error). The message is translation occurrence
  `survey:study_area_message`. Print frames on the area (`print.static_map.resolve_frame`,
  `draw_study_area`, only placed layers drawn); Responses adds it as reference meta `study_area`;
  Reports map blocks carry `payload['study_area']` unless `config.study_area is False`.
- **Section choice (change section-study-area, #781)**: a map section uses the survey's area (default,
  also "no row"), its own, or none — `SectionStudyArea` (canonical survey + section ref, like
  placements; `mode` survey/own/none; a row off `own` keeps its outline). ONE resolver
  `study_area.effective(section)` → `(kind, area)`; every respondent-side reader goes through it:
  `views.study_area_meta(section)` (on `#section-data[data-study-area]` via the `study_area_json`
  filter — no shell `json_script`), `StudyArea.show(map, meta)` swaps/clears per section and
  `initSection()` re-opens on a changed area, `study_area_guard.for_section`, print
  `resolve_frame`/`draw_study_area(image, section, spec)`. Own outline URL =
  `survey_study_area_geojson?section=<id>`. Refusals count on the refusing row. Responses and Reports
  read `get(survey)` only. The survey's area is edited from Survey settings → Respondent map
  (`_survey_study_area.html`); the Map card picks the mode (`editor_study_area_section_mode`); the
  editor endpoints take `section`. Message occurrence `section:<ref>:study_area_message`. ZIP
  `section_study_areas`; REST/MCP `…/sections/{id}/study-area`, `get/set_section_study_area`.

**Reference overlay layers (`SurveyMapLayer`, kill switch `MAP_REFERENCE_LAYERS`)**: creator-uploaded
GeoJSON rendered read-only beneath answer geometry on four surfaces — the respondent map, the editor
preview, the Responses **Map pane**, its **Overview thumbnail** and the per-response **map modal**
(the 200-px drawer thumbnail stays bare). One styling source: `partials/ref_layer_factory.html` (`window.RefLayerFactory.build`)
is included before any consumer; `partials/reference_layers.html` (respondent) and
`editor/partials/analytics_geo_map.html` (Responses) only fetch and place what it builds. Metadata
comes from `survey/layers.py::build_map_layers_metadata`, geometry only from the gated endpoint
`survey_layer_geojson` — never inlined. That endpoint admits any collaborator with the `viewer`
role or above in every survey status (a closed survey is where responses get read); outsiders
still go through `check_survey_access`, which is deliberately untouched. On Responses, layers are
non-interactive whatever `show_popups` says, ignore per-section `hidden_layers` (the map
aggregates all sections), and make the Map pane render even with zero geo answers. On the Map
pane they are `reference` slots of the `LayerManager`, listed in a titled group beneath the
answer layers in the Layers panel (own pane each, so stacking = panel order, never fetch order);
order, visibility and opacity persist in `localStorage['rv2RefLayers:<uuid>']` — browser-only,
never the model. Cap: `MAX_LAYERS_PER_SURVEY = 10`.

**Layer memory rules (change `layer-memory-diet`, after the 2026-09-15 memory-limit incident)**:
`SurveyMapLayer.geojson` is up to 10 MB of text per row, and a gunicorn worker keeps the RSS of
its largest request for life. The text is stored gzip-compressed in `geojson_gz` (a third of the
bytes in the row, in the worker and on the wire); `geojson` is a property that decompresses on
read and compresses on write, so readers and writers (including `create(geojson=…)`) keep the
text API — but `.defer()`, `update_fields` and `.values()` name `geojson_gz`. The gated endpoint
hands the stored bytes to a client that sends `Accept-Encoding: gzip` (every browser and
`fetch()`) with `Content-Encoding: gzip` and decompresses only for one that does not. So
`layers_for()`, `question_layers_for()` and every layer `get_object_or_404` in editor/object views
DEFER `GEOMETRY_TEXT_FIELDS`; the only readers of the text are the gated endpoint
(`_gated_layer(with_geojson=True)`), `download_data` and the ZIP export
(`layers_for(survey).defer(None)`). `question.layer` cannot defer through the FK, and a
full instance's `save()` writes the text back — on respondent and Responses paths use
`layers.layer_lite(question)`. Property names for the editor's pickers are the stored
`SurveyMapLayer.property_names`, written by `rebuild_layer`; never parse the GeoJSON to list
them. Workers recycle after `GUNICORN_MAX_REQUESTS` (+ jitter) requests, and the worker class is
`mapsurvey.gunicorn_workers.DrainingThreadWorker`, NOT stock `gthread`: gthread drops the
connections it accepted in its last loop iteration when it recycles or gets a deploy's SIGTERM
(one 502 per recycle on 2026-09-16); the draining worker stops accepting first and serves what it
holds. `scripts/gunicorn_recycle_check.py` is the reproduction — run it against both classes after
touching the gunicorn command line or bumping gunicorn. The `LayerMemoryDietTest` query-capture
tests fail if a page starts selecting the column again.

**Layer objects (`LayerObject`, `LayerObjectAsset`; change `overlay-features`)**: a layer is a
container of objects — key, title, category, rich-text description, link, one-part geometry,
raw imported properties, ordered attachments (image/audio/document/video files on the PUBLIC
media tier under random `layer_assets/<uuid>` keys, or YouTube/Vimeo embeds). `SurveyMapLayer.geojson`
is a CACHE derived from them (`survey/layers.py::rebuild_layer`, reserved `_key/_title/_category/
_has_content/_cover` properties) — never edit it as a source; `geojson_legacy` holds the FD-1 text
until one release after migration `0068` and then goes. Layers are owned by the CANONICAL survey
and borrowed by draft copies and archived versions through `layers_for()`/`layer_owner()`; nothing
copies them, so an object edit on a published survey is live for respondents (the object editor
says so in a banner). The object editor is a full page, `/editor/surveys/<uuid>/layers/<id>/edit/`
(`survey/layer_object_views.py`, `js/layer_editor.js`), with three ways in — draw, import GeoJSON,
import CSV — plus content CSV and photo batches matched by key, then title. Per-object cards for
respondents come from `survey_layer_object` under the same gate as the layer endpoint.

**Objects on the map (`layer_objects`) and `thumbs`**: `layer_objects` is a question type bound to
one layer (`Question.layer`, PROTECT — the settings card refuses to delete a bound layer and names
the question); `min_objects` replaces `required`. **Sub-questions are the one mechanism** for "ask
about an object on the map", shared by geo questions and `layer_objects` (`PARENT_TYPES`), with two
entry points into the same modal: the *Sub-questions* section inside the question modal and the
"+ Add Sub-question" button under the question. A geo question with no sub-questions is a normal
state — hint, never block. Respondent side = variant A: the panel list (`partials/layer_objects_block.html`)
is navigation; a row or a feature opens the SAME Leaflet popup respondent-placed features use, with
the object card + the sub-question form + ✓, and nothing opens while a draw/crosshair mode is
active. Answers about objects are rows on the sub-questions with `Answer.layer_object` set (partial
unique per session/sub-question/object) and NEVER `parent_answer_id`; they post as `obj__<key>__<code>`
fields. `thumbs` (👍/👎) is a choice type with the fixed `THUMBS_CHOICES` (`1=up`, `0=down`), so
every choice consumer works unchanged. Aggregates on every read surface come from one place,
`survey/object_stats.py`. Variant B (object card in the panel, geo popups moved there too) is
deferred as a future alternative view — do not reintroduce it ad hoc.

**Shared map (`question`-sourced reference layers)**: a `SurveyMapLayer` with
`source='question'` holds no creator objects — its `LayerObject`s are MATERIALISED from
respondents' answers to the geo question named by `source_question_code` (a code, not a FK:
layers belong to the canonical survey, question rows are copied per version). Materialisation
runs at the end of the section POST (`layers.sync_question_layers_for_session`) and keys
objects `s<session>-<n>`, never by answer id, because the POST deletes and re-inserts a
session's answers on every submit and a re-keyed object would lose the reactions other
respondents left on it. Respondents get `build_question_layer_geojson` per request
(`no-store`, own marks omitted, only `status='visible'` from clean sessions); creator
surfaces read the cached `layer.geojson` (every status, clean sessions) rebuilt on
materialisation, moderation and session-status changes. Reactions are ordinary answers to
the sub-questions of an "Objects on the map" question bound to that layer; `show_tallies`,
`show_comments`, `approve_first` on the layer decide what other respondents see, and
`LayerObject.status` / `Answer.hidden` are the creator's per-item moderation. The object
editor is read-only for such layers; deleting the source geo question is refused.

**Coverage surface (change `responses-coverage-surface`, issue #242, epic #245)**: on the Responses
Map pane a LineString/Polygon answer layer's menu offers *Create Coverage*, a `coverage` slot of
the `LayerManager` that draws, per world-anchored metre cell, the share of respondents whose shape
covers it (polygons: inside, holes excluded; lines: within `corridorMeters`, default 20 m). It is
`L.SprayAgreementLayer` (`js/spray_layer.js`) fed `{id, geometry}` members instead of `{id, dots}`
clouds — ONE binning seam (`_bin` → `_rasterise`, an offscreen canvas at cell resolution clipped
to the viewport, even-odd fill, stroke width = corridor in cells, alpha read-back) for spray,
polygons and lines, so the three never disagree; do not add a second density renderer. Each
respondent counts once per cell; the row reads "≤ N of M respondents". Derived in the browser
only — exact counts for export and public results are #243, the agreement contour #244.

**Reference layer style**: `SurveyMapLayer.style` (JSON) holds the base look beyond `color`
(opacity, weight, fill_opacity, radius, icon) and at most one rule `by` one object property
(categories or graduated classes, plus `other`). `layers.normalize_style` is the ONE validator
— the update endpoint and the ZIP cleaner both run it, so a style that saves is a style that
draws; never read `layer.style` raw. `ref_layer_factory.html`'s `styleFor()` is the ONE
renderer (rule class → simplestyle in the file → base) for the respondent map and the
Responses map alike; `layers.match_class` mirrors its matching for the server-side legend
(`legend_for`, delivered as metadata). The object editor draws with its own code and does
not honour rules yet.
